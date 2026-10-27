"""Build and publish brawler stat tierlists from the local catalog."""

import json
import math
import pathlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

import render


@dataclass(frozen=True)
class Stat:
    key: str
    title: str
    rating_key: str | None
    path: tuple[str, ...]
    tiers: tuple[str, ...]


RANGE_TIERS = ('VERY LONG', 'LONG', 'NORMAL', 'SHORT', 'VERY SHORT', 'N/A')
SPEED_TIERS = ('VERY FAST', 'FAST', 'NORMAL', 'SLOW', 'VERY SLOW', 'N/A')
HEALTH_TIERS = ('10000+', '9000', '8000', '7000', '6000', '5000', '5000-')
STATS = (
    Stat('health', 'Health', None, ('health',), HEALTH_TIERS),
    Stat('main-range', 'Main Attack Range', 'rangeMain',
         ('mainAttack', 'range'), RANGE_TIERS),
    Stat('super-range', 'Super Range', 'rangeSuper',
         ('super', 'range'), RANGE_TIERS),
    Stat('movement-speed', 'Movement Speed', 'speed',
         ('speedUnits',), SPEED_TIERS),
    Stat('reload-speed', 'Reload Speed', 'reload',
         ('mainAttack', 'reloadSeconds'), SPEED_TIERS),
)
ROLE_ORDER = ('aggro', 'antiTank', 'controller', 'sniper',
              'support', 'tank', 'thrower', 'Unclassified')
PALETTE = ('#e87582', '#f5c388', '#f9df8b', '#fdff91',
           '#cbfd8e', '#a0fc8f', '#88d8ed')


def _numeric_value(spec, stat):
    value = spec
    for field in stat.path:
        value = value[field]
    if isinstance(value, list):
        if not value:
            raise ValueError(f'{stat.key} values must not be empty')
        candidates = value
    else:
        candidates = [value]
    if any(isinstance(item, bool) or not isinstance(item, (int, float))
           or not math.isfinite(item) for item in candidates):
        raise ValueError(f'{stat.key} must be numeric')
    value = (max(candidates) if stat.key in ('main-range', 'super-range')
             else candidates[0])
    if stat.key == 'reload-speed':
        if value <= 0:
            raise ValueError('reloadSeconds must be positive')
        return 1 / value
    return value


def _health_tier(health):
    if health < 5000:
        return '5000-'
    if health >= 10000:
        return '10000+'
    return str(int(health // 1000) * 1000)


def _rating(spec, stat, value):
    if stat.rating_key is None:
        return _health_tier(value)
    rating = str(spec['rating'][stat.rating_key]).strip()
    return rating if rating == 'N/A' else rating.split('/', 1)[0].strip()


def build_document(catalog, stat):
    """Order both views by rating tier, then numeric value within each tier."""
    records = []
    for name, spec in catalog.items():
        if name == 'version':
            continue
        value = _numeric_value(spec, stat)
        tier = _rating(spec, stat, value)
        if tier not in stat.tiers:
            raise ValueError(f'Unsupported {stat.key} rating {tier!r} for {name}')
        role = spec.get('roles', {}).get('*', '*')
        if role == '*':
            role = 'Unclassified'
        if role not in ROLE_ORDER:
            raise ValueError(f'Unsupported common class {role!r} for {name}')
        records.append((name, value, tier, role))

    tier_order = [tier for tier in stat.tiers
                  if any(record[2] == tier for record in records)]
    tier_rank = {tier: index for index, tier in enumerate(stat.tiers)}
    sorted_records = sorted(
        records,
        key=lambda record: (tier_rank[record[2]], -record[1], record[0]),
    )
    tier_groups = {
        tier: [name for name, _, label, _ in sorted_records if label == tier]
        for tier in tier_order
    }
    role_groups = {
        role: [name for name, _, _, group in sorted_records if group == role]
        for role in ROLE_ORDER if any(record[3] == role for record in records)
    }
    return {
        'source': 'stats',
        'stat': stat.key,
        'title': f'Brawler Tierlist: {stat.title}',
        'tierOrder': tier_order,
        'tierColors': {
            tier: PALETTE[index] for index, tier in enumerate(tier_order)
        },
        'originalTierlist': tier_groups,
        'globalRoles': role_groups,
        'values': {name: value for name, value, _, _ in records},
    }


def find_imagemagick():
    if shutil.which('magick'):
        return ['magick']
    if sys.platform != 'win32' and shutil.which('convert'):
        return ['convert']
    return None


def generate_all(catalog_path, avatar_dir, map_dir, output_dir, resolution=None):
    """Write JSON, SVG, PNG, and ImageMagick JPG for all five stats."""
    render.parse_resolution(resolution)
    magick = find_imagemagick()
    if magick is None:
        raise RuntimeError('ImageMagick was not found on PATH')
    catalog = json.loads(pathlib.Path(catalog_path).read_text(encoding='utf-8'))
    documents = {stat.key: build_document(catalog, stat) for stat in STATS}
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as temp_dir:
        temporary = pathlib.Path(temp_dir)
        for name, document in documents.items():
            json_path = temporary / f'{name}.json'
            svg_path = temporary / f'{name}.svg'
            png_path = temporary / f'{name}.png'
            jpg_path = temporary / f'{name}.jpg'
            json_path.write_text(json.dumps(document, indent=2) + '\n',
                                 encoding='utf-8')
            render.render_document(document, avatar_dir, svg_path, map_dir=map_dir)
            render.render_document(document, avatar_dir, png_path,
                                   resolution=resolution, map_dir=map_dir)
            command = [*magick, str(png_path), '-background', '#2b2b2b',
                       '-alpha', 'remove', '-alpha', 'off', '-quality', '92',
                       str(jpg_path)]
            result = subprocess.run(command, capture_output=True, text=True,
                                    check=False)
            if result.returncode:
                raise RuntimeError(
                    f'ImageMagick failed for {name}: '
                    f'{result.stderr.strip() or result.returncode}')
        for name in documents:
            for suffix, subdir in (('json', 'json'), ('svg', 'svg'),
                                   ('png', 'png'), ('jpg', 'png/jpg')):
                destination = output_dir / subdir / f'{name}.{suffix}'
                destination.parent.mkdir(parents=True, exist_ok=True)
                (temporary / f'{name}.{suffix}').replace(destination)
    return documents
