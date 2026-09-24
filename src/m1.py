"""Canonical data and stable regrouping helpers for the M1 tierlist slice."""

import copy
import re

import kkpyutil as util


GLOBAL_ROLES = (
    'aggro',
    'antiTank',
    'controller',
    'sniper',
    'support',
    'tank',
    'thrower',
)

MODE_ROLES = {
    'bounty': ('range', 'blueStar', 'pressure'),
    'brawlBall': ('damage', 'flex', 'pressure'),
    'gemGrab': ('carrier', 'damage', 'control', 'pressure'),
    'heist': ('safeDamage', 'flex', 'defender'),
    'hotZone': ('zoneTime', 'damage', 'control'),
    'knockout': ('range', 'flex', 'pressure'),
}

_TITLE_PREFIX = re.compile(
    r'^\s*brawl\s+stars\s+tier\s+list\s*[-:–—]+\s*',
    re.IGNORECASE,
)


def normalize_identifier(value):
    """Return a comparison key while preserving canonical names elsewhere."""
    return ''.join(character.casefold() for character in str(value)
                   if character.isalnum())


def normalize_brawler_identifier(value):
    return normalize_identifier(value)


def normalize_role_label(value):
    """Normalize role labels and turn unfinished values into the unknown marker."""
    if value is None:
        return '*'
    label = str(value).strip()
    if not label or label == '*':
        return '*'
    return label


def normalize_map_name(ocr_text, map_catalog):
    """Resolve raw OCR text to a canonical map key from the supplied catalog."""
    lines = [line.strip() for line in str(ocr_text).splitlines() if line.strip()]
    title = next((line for line in lines
                  if 'brawl stars tier list' in line.casefold()), lines[0] if lines else '')
    display_name = _TITLE_PREFIX.sub('', title).strip()
    target = normalize_identifier(display_name)
    for map_name in map_catalog:
        if map_name == 'version':
            continue
        if normalize_identifier(map_name) == target:
            return map_name
    raise KeyError(f'Unable to resolve OCR map name: {display_name!r}')


def load_global_roles(path):
    data = util.load_json(path)
    roles = {}
    for name, role in data.items():
        if name == 'version':
            continue
        normalized_role = normalize_role_label(role.get('roles', {}).get('*'))
        if normalized_role not in GLOBAL_ROLES and normalized_role != '*':
            raise ValueError(f'Unsupported global role {normalized_role!r} for {name!r}')
        roles[normalize_brawler_identifier(name)] = normalized_role
    return roles


def load_mode_roles(path):
    """Load per-mode labels, normalizing blank metadata to ``*``."""
    data = util.load_json(path)
    result = {}
    for name, spec in data.items():
        if name == 'version':
            continue
        raw_roles = spec.get('roles', {})
        result[normalize_brawler_identifier(name)] = {
            mode: normalize_role_label(role)
            for mode, role in raw_roles.items()
            if mode != '*'
        }
    return result


def _ordered_roles(roles):
    return sorted(roles, key=lambda role: (role == '*', role))


def group_brawlers_by_role(tierlist, roles):
    """Group brawlers without changing their source-tier appearance order."""
    grouped = {}
    for names in tierlist.values():
        for name in names:
            role = normalize_role_label(roles.get(normalize_brawler_identifier(name), '*'))
            grouped.setdefault(role, []).append(name)
    return {role: grouped[role] for role in _ordered_roles(grouped)}


def build_master_document(tierlist, map_name, mode, global_roles, mode_roles):
    """Build the M1 JSON document with independent global and map-role views."""
    selected_mode_roles = {
        name: roles.get(mode, '*') for name, roles in mode_roles.items()
    }
    return {
        'map': map_name,
        'mode': mode,
        'originalTierlist': copy.deepcopy(tierlist),
        'globalRoles': group_brawlers_by_role(tierlist, global_roles),
        'mapRoles': group_brawlers_by_role(tierlist, selected_mode_roles),
    }