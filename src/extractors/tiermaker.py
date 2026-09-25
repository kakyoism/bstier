"""TierMaker-specific adaptive grid extraction strategy."""

import cv2
import numpy as np

from .base import ExtractedTierlist, TierlistExtractor
from .common import (
    detect_header_column,
    detect_tiermaker_regions,
    estimate_grid_period,
    load_asset_descriptors,
    load_brawler_catalog,
)
from .labels import recognize_tier_label


class TierMakerExtractor(TierlistExtractor):
    """Extract square TierMaker tiles without fixture-sized constants."""

    min_good_matches = 4
    ratio_test = 0.75

    def extract(self, image_path):
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f'Unable to load tierlist image: {image_path}')
        header = detect_header_column(image)
        regions = detect_tiermaker_regions(image, header)
        if not regions:
            raise ValueError('Unable to detect TierMaker tier rows')

        labels = []
        for x, y, width, height in regions:
            label = recognize_tier_label(
                image[y:y + height, x:x + width],
                self.context.tier_label_adapter,
            )
            if label in labels:
                raise ValueError(f'Duplicate TierMaker tier label: {label}')
            labels.append(label)

        catalog = load_brawler_catalog(self.context.brawler_spec_path)
        detector, assets = load_asset_descriptors(
            self.context.avatar_dir, catalog)
        matcher = cv2.BFMatcher(cv2.NORM_L2)
        period = estimate_grid_period(image, header[1])
        candidates = []
        for row in range((image.shape[0] + period - 1) // period):
            for column in range(
                    (image.shape[1] - header[1] + period - 1) // period):
                tile = image[
                    row * period:min((row + 1) * period, image.shape[0]),
                    header[1] + column * period:
                    min(header[1] + (column + 1) * period, image.shape[1]),
                ]
                if (tile.shape[1] < period * 0.8
                        or tile.shape[0] < period * 0.8):
                    continue
                # TierMaker exports leave dark empty cells and may include
                # branding in the first row. Avatar cells occupy most of
                # their square, unlike those decorative regions.
                if np.mean(tile > 30) < 0.4:
                    continue
                tile = self._pad_tile(tile, period)
                _, descriptors = detector.detectAndCompute(
                    cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY), None)
                if descriptors is None:
                    continue
                best = self._match_tile(descriptors, assets, matcher)
                if best is None or best[0] < self.min_good_matches:
                    continue
                center_y = row * period + period / 2
                region_index = next(
                    (index for index, (_, y, _, height) in enumerate(regions)
                     if y <= center_y < y + height),
                    None,
                )
                if region_index is not None:
                    candidates.append((*best, row, column, region_index))

        selected = []
        used_names = set()
        for score, name, row, column, region_index in sorted(
                candidates, key=lambda item: item[0], reverse=True):
            if name in used_names:
                continue
            used_names.add(name)
            selected.append((row, column, region_index, name))

        tiers = {label: [] for label in labels}
        for row, column, region_index, name in sorted(selected):
            tiers[labels[region_index]].append(name)
        return ExtractedTierlist(tiers)

    @staticmethod
    def _pad_tile(tile, period):
        if tile.ndim == 2:
            shape = (period, period)
        else:
            shape = (period, period, tile.shape[2])
        padded = np.zeros(shape, dtype=tile.dtype)
        padded[:tile.shape[0], :tile.shape[1]] = tile
        return padded

    def _match_tile(self, descriptors, assets, matcher):
        best = None
        for name, asset_descriptors in assets:
            matches = matcher.knnMatch(descriptors, asset_descriptors, k=2)
            good = [
                pair[0] for pair in matches
                if len(pair) == 2
                and pair[0].distance < self.ratio_test * pair[1].distance
            ]
            score = len(good)
            if best is None or score > best[0]:
                best = (score, name)
        return best