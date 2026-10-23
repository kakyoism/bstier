"""TierMaker-specific adaptive grid extraction strategy."""

import cv2
import numpy as np

from .base import ExtractedTierlist, TierlistExtractor
from .common import (
    BrawlerMatcher,
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
        tier_colors = {}
        for x, y, width, height in regions:
            label = recognize_tier_label(
                image[y:y + height, x:x + width],
                self.context.tier_label_adapter,
            )
            if label in labels:
                raise ValueError(f'Duplicate TierMaker tier label: {label}')
            labels.append(label)
            # Sample the plain left margin, away from the centered label glyph.
            color_sample = image[
                y + height // 4:y + 3 * height // 4,
                x + max(1, width // 10):x + max(2, width // 4),
            ]
            blue, green, red = np.median(
                color_sample.reshape(-1, 3), axis=0).astype('uint8')
            tier_colors[label] = f'#{red:02x}{green:02x}{blue:02x}'

        catalog = load_brawler_catalog(self.context.brawler_spec_path)
        detector, assets = load_asset_descriptors(
            self.context.avatar_dir, catalog)
        matcher = BrawlerMatcher(
            detector, assets, self.ratio_test, use_variants=True)
        period = estimate_grid_period(image, header[1])
        tiles = []
        for row in range((image.shape[0] + period - 1) // period):
            for column in range(
                    (image.shape[1] - header[1] + period - 1) // period):
                tile = image[
                    row * period:min((row + 1) * period, image.shape[0]),
                    header[1] + column * period:
                    min(header[1] + (column + 1) * period, image.shape[1]),
                ]
                # TierMaker images may crop the last row slightly below a
                # complete grid cell. Keep that row when enough avatar remains.
                min_height = period * (0.7 if (row + 1) * period > image.shape[0]
                                       else 0.8)
                if (tile.shape[1] < period * 0.8
                        or tile.shape[0] < min_height):
                    continue
                # TierMaker exports leave dark empty cells and may include
                # branding in the first row. Avatar cells occupy most of
                # their square, unlike those decorative regions.
                if np.mean(tile > 30) < 0.4:
                    continue
                tile = self._pad_tile(tile, period)
                center_y = row * period + period / 2
                region_index = next(
                    (index for index, (_, y, _, height) in enumerate(regions)
                     if y <= center_y < y + height),
                    None,
                )
                if region_index is not None:
                    tiles.append(((row, column, region_index), tile))

        selected = matcher.assign(tiles, self.min_good_matches)

        tiers = {label: [] for label in labels}
        for row, column, region_index in sorted(selected):
            tiers[labels[region_index]].append(
                selected[(row, column, region_index)][1])
        return ExtractedTierlist(tiers, tier_colors)

    @staticmethod
    def _pad_tile(tile, period):
        if tile.ndim == 2:
            shape = (period, period)
        else:
            shape = (period, period, tile.shape[2])
        padded = np.zeros(shape, dtype=tile.dtype)
        padded[:tile.shape[0], :tile.shape[1]] = tile
        return padded
