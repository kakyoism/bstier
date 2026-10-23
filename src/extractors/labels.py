"""Tier-label normalization shared by DeepDraft and TierMaker."""

import re
from collections import Counter


VALID_TIER_LABELS = frozenset({'S+', 'S', 'A', 'B', 'C', 'D', 'F'})


def normalize_tier_label(value):
    text = str(value).upper().replace('＋', '+')
    text = re.sub(r'[^SABCDF+]', '', text)
    if 'S+' in text:
        return 'S+'
    for label in ('S', 'A', 'B', 'C', 'D', 'F'):
        if label in text:
            return label
    return None


def recognize_tier_label(crop, adapter):
    raw_values = adapter(crop)
    if isinstance(raw_values, str):
        raw_values = [raw_values]
    labels = [normalize_tier_label(value) for value in raw_values]
    valid_labels = [label for label in labels if label in VALID_TIER_LABELS]
    if valid_labels:
        # The OCR adapter tries several image variants. An early variant can
        # misread a letter even when the remaining variants agree.
        counts = Counter(valid_labels)
        return max(counts, key=counts.get)
    raise ValueError('Unable to recognize tier label')
