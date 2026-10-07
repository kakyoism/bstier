#!/usr/bin/env python3
"""Batch-extract and render DeepDraft tierlist images."""

import argparse
import json
import pathlib
import shutil
import sys
import types

from PIL import Image, ImageOps


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

import core


IMAGE_SUFFIXES = {'.bmp', '.jpeg', '.jpg', '.png', '.webp'}
OUTPUT_DIRS = ('json', 'svg', 'png', 'org')
MAP_DIR = PROJECT_ROOT / 'res' / 'map'
STITCH_BACKGROUND_COLOR = (43, 43, 43)


def discover_images(input_dir):
    """Return supported image files directly inside ``input_dir``."""
    input_dir = pathlib.Path(input_dir)
    if not input_dir.is_dir():
        raise ValueError(f'Input folder does not exist: {input_dir}')
    images = sorted(
        path for path in input_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
    )
    if not images:
        raise ValueError(f'No supported images found in: {input_dir}')
    stems = [path.stem.casefold() for path in images]
    if len(stems) != len(set(stems)):
        raise ValueError('Input images must have unique basenames')
    return images


def output_paths(input_dir, image_path):
    """Return the JSON destination for one input image."""
    stem = image_path.stem
    return {'json': input_dir / 'json' / f'{stem}.json'}


def _normalize_identifier(value):
    return ''.join(character.casefold() for character in str(value)
                   if character.isalnum())


def stitched_output_path(input_dir, mode, map_name):
    """Return the lowercase mode-map PNG destination for an M1 document."""
    if mode is None or map_name is None:
        raise ValueError('The M1 document must include both mode and map')
    mode_name = str(mode).strip().casefold()
    map_name = str(map_name).strip().casefold()
    if not mode_name or not map_name:
        raise ValueError('The M1 document must include both mode and map')
    return pathlib.Path(input_dir) / 'org' / f'{mode_name}-{map_name}.png'


def image_output_paths(input_dir, mode, map_name):
    """Return all image destinations using the lowercase mode-map stem."""
    org_path = stitched_output_path(input_dir, mode, map_name)
    stem = org_path.stem
    return {
        'svg': pathlib.Path(input_dir) / 'svg' / f'{stem}.svg',
        'png': pathlib.Path(input_dir) / 'png' / f'{stem}.png',
        'org': org_path,
    }


def find_map_image(map_name, map_dir=None):
    """Find the map artwork whose filename matches a canonical map name."""
    map_dir = pathlib.Path(map_dir or MAP_DIR)
    map_key = _normalize_identifier(map_name)
    for path in sorted(map_dir.iterdir()):
        if (path.is_file()
                and path.suffix.casefold() in {'.png', '.jpg', '.jpeg'}
                and _normalize_identifier(path.stem) == map_key):
            return path
    raise FileNotFoundError(f'No map image found for {map_name!r} in {map_dir}')


def _opaque_rgb(image, background_color=STITCH_BACKGROUND_COLOR):
    rgba_image = image.convert('RGBA')
    background = Image.new(
        'RGBA', rgba_image.size, (*background_color, 255))
    background.alpha_composite(rgba_image)
    return background.convert('RGB')


def stitch_map_and_tierlist(map_path, tierlist_path, output_path):
    """Write a PNG with the map at left and tierlist at right, height-aligned."""
    with Image.open(map_path) as source_map:
        map_image = _opaque_rgb(ImageOps.exif_transpose(source_map))
    with Image.open(tierlist_path) as source_tierlist:
        tierlist_image = _opaque_rgb(ImageOps.exif_transpose(source_tierlist))

    if map_image.height != tierlist_image.height:
        map_width = max(
            1,
            round(map_image.width * tierlist_image.height / map_image.height),
        )
        map_image = map_image.resize(
            (map_width, tierlist_image.height), Image.Resampling.LANCZOS)

    stitched = Image.new(
        'RGB',
        (map_image.width + tierlist_image.width, tierlist_image.height),
        STITCH_BACKGROUND_COLOR,
    )
    stitched.paste(map_image, (0, 0))
    stitched.paste(tierlist_image, (map_image.width, 0))
    stitched.save(output_path, format='PNG')


def clear_outputs(input_dir):
    """Remove all previous batch outputs while preserving their directories."""
    for name in OUTPUT_DIRS:
        output_dir = pathlib.Path(input_dir) / name
        if output_dir.is_symlink() or output_dir.is_file():
            output_dir.unlink()
        elif output_dir.is_dir():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)


def _run_extract(image_path, json_path):
    args = types.SimpleNamespace(
        command='extract',
        fromPath=str(image_path),
        toPath=str(json_path),
        source='deepdraft',
        title=None,
        master=True,
    )
    result, _ = core.main(args)
    if not result.ok:
        raise RuntimeError(result.detail or 'DeepDraft extraction failed')


def _run_generate(json_path, output_path, resolution):
    args = types.SimpleNamespace(
        command='generate',
        fromPath=str(json_path),
        toPath=str(output_path),
        reso=resolution,
    )
    result, _ = core.main(args)
    if not result.ok:
        raise RuntimeError(result.detail or 'Tierlist rendering failed')


def process_image(image_path, input_dir, resolution=None):
    """Extract and render one image, returning its output paths."""
    paths = output_paths(input_dir, image_path)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    _run_extract(image_path, paths['json'])
    document = json.loads(paths['json'].read_text(encoding='utf-8'))
    map_name = document.get('map')
    mode = document.get('mode')
    image_paths = image_output_paths(input_dir, mode, map_name)
    paths.update(image_paths)
    paths['org'].parent.mkdir(parents=True, exist_ok=True)
    paths['svg'].parent.mkdir(parents=True, exist_ok=True)
    paths['png'].parent.mkdir(parents=True, exist_ok=True)
    if paths['org'].exists():
        raise FileExistsError(
            f'Multiple input images resolve to the same stitched output: '
            f'{paths["org"]}')
    map_path = find_map_image(map_name)
    stitch_map_and_tierlist(map_path, image_path, paths['org'])
    _run_generate(paths['json'], paths['svg'], resolution)
    _run_generate(paths['json'], paths['png'], resolution)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Batch-process DeepDraft tierlist images.',
    )
    parser.add_argument(
        'input_folder',
        help='Folder containing DeepDraft tierlist images.',
    )
    parser.add_argument(
        '--reso',
        help='PNG resolution in WIDTHxHEIGHT format; uses the default otherwise.',
    )
    args = parser.parse_args(argv)

    input_dir = pathlib.Path(args.input_folder).expanduser().resolve()
    try:
        images = discover_images(input_dir)
    except ValueError as exc:
        parser.error(str(exc))

    clear_outputs(input_dir)

    failures = []
    for image_path in images:
        print(f'Processing {image_path.name}...')
        try:
            paths = process_image(image_path, input_dir, args.reso)
        except Exception as exc:  # Keep processing the remaining images.
            failures.append((image_path.name, exc))
            print(f'  FAILED: {exc}', file=sys.stderr)
            continue
        print(f'  JSON: {paths["json"]}')
        print(f'  SVG:  {paths["svg"]}')
        print(f'  PNG:  {paths["png"]}')
        print(f'  ORG:  {paths["org"]}')

    print(f'Processed {len(images) - len(failures)}/{len(images)} image(s).')
    if failures:
        print('Failed images:', file=sys.stderr)
        for name, error in failures:
            print(f'  {name}: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())