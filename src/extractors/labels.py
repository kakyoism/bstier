"""Tier-label normalization shared by DeepDraft and TierMaker."""

import re


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
    for raw_value in raw_values:
        label = normalize_tier_label(raw_value)
        if label in VALID_TIER_LABELS:
            return label
    raise ValueError('Unable to recognize tier label')