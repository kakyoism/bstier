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