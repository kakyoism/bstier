"""DeepDraft-specific tierlist extraction strategy."""

import os
import os.path as osp

import cv2

from .base import ExtractedTierlist, TierlistExtractor
from .common import (
    BrawlerMatcher,
    detect_deepdraft_regions,
    detect_header_column,
    load_asset_descriptors,
    load_brawler_catalog,
    normalize_identifier,
)
from .labels import recognize_tier_label


DEEPDRAFT_TIER_ORDERS = (
    ('S', 'A', 'B', 'C', 'D', 'F'),
    ('S+', 'S', 'A', 'B', 'C', 'D', 'F'),
)


def resolve_deepdraft_tier_labels(labels):
    """Repair one OCR duplicate using DeepDraft's fixed vertical tier order.

    DeepDraft rows are ordered from the highest tier through F, with S+
    optional. If OCR confuses one row with another, retain the OCR result
    unless exactly one expected label is missing and the missing label belongs
    at the duplicated row's position.
    """
    tier_order = next(
        (order for order in DEEPDRAFT_TIER_ORDERS if len(order) == len(labels)),
        None,
    )
    if tier_order is None:
        return labels

    missing = [label for label in tier_order if label not in labels]
    if len(missing) != 1:
        return labels

    duplicate_positions = [
        index for index, label in enumerate(labels)
        if labels.count(label) > 1
    ]
    expected_position = tier_order.index(missing[0])
    if expected_position not in duplicate_positions:
        return labels

    resolved = list(labels)
    resolved[expected_position] = missing[0]
    return resolved


class DeepDraftExtractor(TierlistExtractor):
    """Extract DeepDraft's wide rows using its template-matching layout."""

    template_scale = 0.55
    match_threshold = 0.40

    def extract(self, image_path):
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f'Unable to load tierlist image: {image_path}')

        header = detect_header_column(image)
        regions = detect_deepdraft_regions(image, header)
        if not regions:
            raise ValueError('Unable to detect DeepDraft tier rows')

        labels = []
        for x, y, width, height in regions:
            crop = image[y:y + height, x:x + width]
            labels.append(recognize_tier_label(
                crop, self.context.tier_label_adapter))

        labels = resolve_deepdraft_tier_labels(labels)
        tier_boundaries = {}
        for (x, y, width, height), label in zip(regions, labels):
            if label in tier_boundaries:
                raise ValueError(f'Duplicate DeepDraft tier label: {label}')
            tier_boundaries[label] = (y, y + height)

        catalog = load_brawler_catalog(self.context.brawler_spec_path)
        detector, assets = load_asset_descriptors(
            self.context.avatar_dir, catalog)
        matcher = BrawlerMatcher(detector, assets)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        tiles = []
        for path in sorted(os.listdir(self.context.avatar_dir)):
            if osp.splitext(path)[1].casefold() not in {'.png', '.jpg', '.jpeg'}:
                continue
            name = catalog.get(normalize_identifier(osp.splitext(path)[0]))
            if name is None:
                continue
            template = cv2.imread(
                osp.join(self.context.avatar_dir, path), cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue
            width = int(template.shape[1] * self.template_scale)
            height = int(template.shape[0] * self.template_scale)
            if width < 5 or height < 5:
                continue
            resized = cv2.resize(template, (width, height))
            match = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
            _, score, _, location = cv2.minMaxLoc(match)
            if score < self.match_threshold:
                continue
            center_y = location[1] + height / 2
            region_index = None
            for index, (label, (y_min, y_max)) in enumerate(
                    tier_boundaries.items()):
                if y_min <= center_y < y_max:
                    region_index = index
                    break
            if region_index is None:
                continue
            tile = image[
                location[1]:location[1] + height,
                location[0]:location[0] + width,
            ]
            tiles.append(((location[0], location[1], region_index), tile))

        selected = matcher.assign(tiles, 1)

        tiers = {label: [] for label in tier_boundaries}
        for x, y, region_index in sorted(
                selected, key=lambda key: (key[1] // 40, key[0])):
            label = list(tier_boundaries)[region_index]
            tiers[label].append(selected[(x, y, region_index)][1])
        return ExtractedTierlist(tiers)