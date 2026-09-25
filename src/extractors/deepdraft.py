"""DeepDraft-specific tierlist extraction strategy."""

import os
import os.path as osp

import cv2

from .base import ExtractedTierlist, TierlistExtractor
from .common import (
    detect_deepdraft_regions,
    detect_header_column,
    load_brawler_catalog,
    normalize_identifier,
)
from .labels import recognize_tier_label


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

        tier_boundaries = {}
        for x, y, width, height in regions:
            crop = image[y:y + height, x:x + width]
            label = recognize_tier_label(
                crop, self.context.tier_label_adapter)
            if label in tier_boundaries:
                raise ValueError(f'Duplicate DeepDraft tier label: {label}')
            tier_boundaries[label] = (y, y + height)

        catalog = load_brawler_catalog(self.context.brawler_spec_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        results = {label: [] for label in tier_boundaries}
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
            for label, (y_min, y_max) in tier_boundaries.items():
                if y_min <= center_y < y_max:
                    results[label].append((location[0], location[1], name))
                    break

        return ExtractedTierlist({
            label: [
                name for _, _, name in sorted(
                    items, key=lambda item: (item[1] // 40, item[0]))
            ]
            for label, items in results.items()
        })