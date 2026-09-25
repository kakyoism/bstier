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
    'bounty': ('range', 'blueStar/pressure'),
    'brawlBall': ('damage', 'flex', 'pressure'),
    'gemGrab': ('carrier', 'damage', 'control', 'pressure'),
    'heist': ('safeDamage', 'flex', 'defence'),
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
    map_names = [name for name in map_catalog if name != 'version']
    for map_name in map_names:
        if normalize_identifier(map_name) == target:
            return map_name

    # OCR can corrupt surrounding title text while preserving the map name.
    # Match only known catalog names and prefer the most specific match.
    for line in lines:
        line_target = normalize_identifier(line)
        matches = [
            map_name for map_name in map_names
            if normalize_identifier(map_name) in line_target
        ]
        if matches:
            return max(matches, key=lambda name: len(normalize_identifier(name)))

    raise KeyError(f'Unable to resolve OCR map name: {display_name!r}')


def resolve_map_context(map_name, map_catalog):
    """Return canonical map, mode, and normalized tags from the map catalog."""
    target = normalize_identifier(map_name)
    canonical_name = next(
        (name for name in map_catalog
         if name != 'version' and normalize_identifier(name) == target),
        None,
    )
    if canonical_name is None:
        raise KeyError(f'Unknown map {map_name!r}')

    map_spec = map_catalog[canonical_name]
    if not isinstance(map_spec, dict):
        raise ValueError(f'Map metadata for {canonical_name!r} must be an object')

    mode = map_spec.get('mode')
    if mode not in MODE_ROLES:
        raise ValueError(
            f'Unsupported or missing mode {mode!r} for {canonical_name!r}')

    raw_tags = map_spec.get('tags', map_spec.get('tag', []))
    if isinstance(raw_tags, str):
        tags = [raw_tags]
    elif isinstance(raw_tags, list):
        tags = copy.deepcopy(raw_tags)
    else:
        raise ValueError(f'Map tags for {canonical_name!r} must be a list or string')

    return {
        'map': canonical_name,
        'mode': mode,
        'tags': tags,
    }


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


def build_global_document(tierlist, title, global_roles):
    """Build the M2 document for a title-bearing, map-independent tierlist."""
    return {
        'title': str(title).strip(),
        'originalTierlist': copy.deepcopy(tierlist),
        'globalRoles': group_brawlers_by_role(tierlist, global_roles),
    }


def build_master_document_from_ocr(
        tierlist, image_path, ocr_adapter, map_catalog, global_roles, mode_roles):
    """Build the M1 document using raw map-title text from an OCR adapter.

    ``ocr_adapter`` receives ``image_path`` and returns raw OCR text. The
    adapter is intentionally injected so OCR backends remain separate from
    canonical map lookup and role grouping.
    """
    ocr_text = ocr_adapter(image_path)
    map_name = normalize_map_name(ocr_text, map_catalog)
    context = resolve_map_context(map_name, map_catalog)
    return build_master_document(
        tierlist,
        context['map'],
        context['mode'],
        global_roles,
        mode_roles,
    )