"""Small image and catalog helpers shared by extraction strategies."""

import pathlib

import cv2
import numpy as np
import kkpyutil as util


def normalize_identifier(value):
    return ''.join(character.casefold() for character in str(value)
                   if character.isalnum())


def load_brawler_catalog(path):
    data = util.load_json(path)
    return {
        normalize_identifier(name): name
        for name in data
        if name != 'version'
    }


def _merge_runs(runs, max_gap):
    merged = []
    for start, end in runs:
        if merged and start - merged[-1][1] <= max_gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def detect_header_column(image):
    """Find the colored tier-label column without using image dimensions."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    colored = (hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 100)
    coverage = colored.mean(axis=0)
    limit = max(1, int(image.shape[1] * 0.4))
    threshold = max(0.45, float(coverage[:limit].max()) * 0.65)
    mask = coverage[:limit] >= threshold
    starts = np.where(mask & ~np.r_[False, mask[:-1]])[0]
    ends = np.where(mask & ~np.r_[mask[1:], False])[0] + 1
    runs = _merge_runs(
        list(zip(starts.tolist(), ends.tolist())),
        max(2, image.shape[1] // 200),
    )
    runs = [run for run in runs if run[1] - run[0] >= image.shape[1] * 0.02]
    if not runs:
        raise ValueError('Unable to detect a colored tier-label column')
    return max(runs, key=lambda run: run[1] - run[0])


def detect_deepdraft_regions(image, header):
    """Detect separated DeepDraft colored header rectangles."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 100)).astype('uint8') * 255
    x_start, x_end = header
    contours, _ = cv2.findContours(
        mask[:, x_start:x_end], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width >= (x_end - x_start) * 0.3 and height >= image.shape[0] * 0.03:
            regions.append((x_start + x, y, width, height))
    return sorted(regions, key=lambda region: region[1])


def detect_tiermaker_regions(image, header):
    """Detect TierMaker row bands from color transitions in the header."""
    x_start, x_end = header
    row_colors = np.median(image[:, x_start:x_end], axis=1).astype('float32')
    window = max(2, int(image.shape[0] * 0.015))
    differences = np.zeros(image.shape[0], dtype='float32')
    for y in range(window, image.shape[0] - window):
        before = row_colors[y - window:y].mean(axis=0)
        after = row_colors[y:y + window].mean(axis=0)
        differences[y] = np.linalg.norm(before - after)

    threshold = max(5.0, float(np.percentile(differences, 90)))
    candidates = [
        y for y in range(1, image.shape[0] - 1)
        if differences[y] >= threshold
        and differences[y] >= differences[y - 1]
        and differences[y] >= differences[y + 1]
    ]
    min_distance = max(10, int(image.shape[0] * 0.06))
    boundaries = []
    for y in sorted(candidates, key=lambda value: differences[value], reverse=True):
        if all(abs(y - boundary) >= min_distance for boundary in boundaries):
            boundaries.append(y)
    boundaries = sorted([0, *boundaries, image.shape[0]])
    regions = []
    for start, end in zip(boundaries, boundaries[1:]):
        if end - start >= image.shape[0] * 0.04:
            regions.append((x_start, start, x_end - x_start, end - start))
    return regions


def estimate_grid_period(image, x_start):
    """Estimate a repeated square tile period from vertical image edges."""
    gray = cv2.cvtColor(image[:, x_start:], cv2.COLOR_BGR2GRAY)
    signal = np.abs(np.diff(gray.astype('float32'), axis=0)).mean(axis=1)
    signal -= signal.mean()
    low = max(8, int(image.shape[0] * 0.04))
    high = max(low + 1, int(image.shape[0] * 0.25))
    scores = [
        (float(np.dot(signal[:-period], signal[period:])), period)
        for period in range(low, min(high, len(signal)))
    ]
    if not scores:
        raise ValueError('Unable to estimate TierMaker tile size')
    return max(scores)[1]


def load_asset_descriptors(avatar_dir, catalog):
    detector = cv2.SIFT_create()
    assets = []
    for path in sorted(pathlib.Path(avatar_dir).iterdir()):
        if path.suffix.casefold() not in {'.png', '.jpg', '.jpeg'}:
            continue
        name = catalog.get(normalize_identifier(path.stem))
        if name is None:
            continue
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            continue
        keypoints, descriptors = detector.detectAndCompute(image, None)
        if descriptors is not None:
            assets.append((name, descriptors))
    return detector, assets


def rank_descriptor_candidates(descriptors, assets, matcher, ratio_test):
    """Return all descriptor candidates ordered by match score."""
    candidates = []
    for asset_index, (name, asset_descriptors) in enumerate(assets):
        matches = matcher.knnMatch(descriptors, asset_descriptors, k=2)
        score = sum(
            len(pair) == 2
            and pair[0].distance < ratio_test * pair[1].distance
            for pair in matches
        )
        candidates.append((score, name, asset_index))
    return sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)


def assign_unique_candidates(candidate_sets, min_score):
    """Assign at most one tile to each name using maximum total confidence.

    ``candidate_sets`` contains ``(tile_key, candidates)`` pairs, where each
    candidate is ``(score, name, asset_index)``. Candidates below
    ``min_score`` are treated as unavailable. The assignment uses a Hungarian
    maximum-weight matching with dummy columns so weak tiles may remain
    unassigned instead of receiving arbitrary names.
    """
    candidates_by_tile = {
        tile_key: [candidate for candidate in candidates
                   if candidate[0] >= min_score]
        for tile_key, candidates in candidate_sets
    }
    tile_keys = list(candidates_by_tile)
    names = sorted({
        name
        for candidates in candidates_by_tile.values()
        for _, name, _ in candidates
    })
    if not tile_keys or not names:
        return {}

    name_columns = {name: index for index, name in enumerate(names)}
    column_count = len(names) + len(tile_keys)
    max_score = max(
        (candidate[0] for candidates in candidates_by_tile.values()
         for candidate in candidates),
        default=0,
    )
    score_scale = 1000
    weights = []
    for tile_key in tile_keys:
        row = [0] * column_count
        candidates = candidates_by_tile[tile_key]
        for rank, (score, name, _) in enumerate(candidates):
            # The score dominates; candidate rank provides deterministic
            # tie-breaking without changing the preferred score materially.
            weight = score * score_scale + len(candidates) - rank
            column = name_columns[name]
            row[column] = max(row[column], weight)
        weights.append(row)

    assignment = _maximum_weight_assignment(weights, max_score * score_scale)
    selected = {}
    for row_index, column in enumerate(assignment):
        if column >= len(names) or weights[row_index][column] <= 0:
            continue
        name = names[column]
        score = next(
            score for score, candidate_name, _ in candidates_by_tile[
                tile_keys[row_index]]
            if candidate_name == name
        )
        selected[tile_keys[row_index]] = (score, name)
    return selected


def _maximum_weight_assignment(weights, absent_weight):
    """Return a row-to-column assignment using the Hungarian algorithm."""
    row_count = len(weights)
    column_count = len(weights[0]) if weights else 0
    costs = [
        [absent_weight - weight for weight in row]
        for row in weights
    ]
    potentials_rows = [0] * (row_count + 1)
    potentials_columns = [0] * (column_count + 1)
    column_owner = [0] * (column_count + 1)
    previous_column = [0] * (column_count + 1)

    for row_index in range(1, row_count + 1):
        column_owner[0] = row_index
        current_column = 0
        minimum_cost = [float('inf')] * (column_count + 1)
        used_columns = [False] * (column_count + 1)
        while True:
            used_columns[current_column] = True
            current_row = column_owner[current_column]
            delta = float('inf')
            next_column = 0
            for candidate_column in range(1, column_count + 1):
                if used_columns[candidate_column]:
                    continue
                reduced_cost = (
                    costs[current_row - 1][candidate_column - 1]
                    - potentials_rows[current_row]
                    - potentials_columns[candidate_column]
                )
                if reduced_cost < minimum_cost[candidate_column]:
                    minimum_cost[candidate_column] = reduced_cost
                    previous_column[candidate_column] = current_column
                if minimum_cost[candidate_column] < delta:
                    delta = minimum_cost[candidate_column]
                    next_column = candidate_column
            for candidate_column in range(column_count + 1):
                if used_columns[candidate_column]:
                    potentials_rows[column_owner[candidate_column]] += delta
                    potentials_columns[candidate_column] -= delta
                else:
                    minimum_cost[candidate_column] -= delta
            current_column = next_column
            if column_owner[current_column] == 0:
                break
        while True:
            prior_column = previous_column[current_column]
            column_owner[current_column] = column_owner[prior_column]
            current_column = prior_column
            if current_column == 0:
                break

    assignment = [-1] * row_count
    for column in range(1, column_count + 1):
        if column_owner[column] != 0:
            assignment[column_owner[column] - 1] = column - 1
    return assignment


class BrawlerMatcher:
    """Shared SIFT tile matcher and one-to-one assignment strategy."""

    def __init__(self, detector, assets, ratio_test=0.75, use_variants=False):
        self.detector = detector
        self.assets = assets
        self.ratio_test = ratio_test
        self.use_variants = use_variants
        self.matcher = cv2.BFMatcher(cv2.NORM_L2)

    def candidates(self, tile):
        candidate_scores = {}
        variants = self._tile_variants(tile)
        for variant in variants:
            if variant.ndim == 3:
                variant = cv2.cvtColor(variant, cv2.COLOR_BGR2GRAY)
            _, descriptors = self.detector.detectAndCompute(variant, None)
            if descriptors is None:
                continue
            for score, name, asset_index in rank_descriptor_candidates(
                    descriptors, self.assets, self.matcher, self.ratio_test):
                current = candidate_scores.get(name)
                if current is None or score > current[0]:
                    candidate_scores[name] = (score, asset_index)
        return sorted(
            (score, name, asset_index)
            for name, (score, asset_index) in candidate_scores.items()
        )[::-1]

    def _tile_variants(self, tile):
        if not self.use_variants:
            return [tile]
        variants = [tile]
        height, width = tile.shape[:2]
        for border in (2, 4, 6):
            if height <= border * 2 or width <= border * 2:
                continue
            inner = tile[border:-border, border:-border]
            variants.append(cv2.resize(
                inner, (width, height), interpolation=cv2.INTER_AREA))
        return variants

    def candidate_sets(self, tiles):
        """Return ranked candidates for ``(tile_key, tile_image)`` pairs."""
        return [
            (tile_key, self.candidates(tile))
            for tile_key, tile in tiles
        ]

    def assign(self, tiles, min_score):
        """Match ``(tile_key, tile_image)`` pairs with unique brawler names."""
        return assign_unique_candidates(
            self.candidate_sets(tiles), min_score)