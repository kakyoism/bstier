#!/usr/bin/env python3
"""Batch-extract and render TierMaker Common Classes tierlists."""

import argparse
import pathlib
import sys
import tempfile
import types


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))
sys.path.insert(0, str(PROJECT_ROOT / 'ci'))

import core
import render
from deepdraft import (IMAGE_SUFFIXES, convert_png_to_jpg, discover_images,
                       find_imagemagick)


def input_images(input_path):
    """Accept one supported image or all supported images in a folder."""
    input_path = pathlib.Path(input_path).expanduser().resolve()
    if input_path.is_file():
        if input_path.suffix.casefold() not in IMAGE_SUFFIXES:
            raise ValueError(f'Unsupported image format: {input_path}')
        return [input_path]
    return discover_images(input_path)


def output_paths(image_path):
    """Keep TierMaker outputs separate from DeepDraft batch outputs."""
    root = image_path.parent / 'tiermaker'
    stem = image_path.stem
    return {
        'json': root / 'json' / f'{stem}.json',
        'svg': root / 'svg' / f'{stem}.svg',
        'png': root / 'png' / f'{stem}.png',
        'jpg': root / 'png' / 'jpg' / f'{stem}.jpg',
    }


def _run_extract(image_path, json_path, title):
    args = types.SimpleNamespace(
        command='extract', fromPath=str(image_path), toPath=str(json_path),
        source='tiermaker', title=title, master=False,
    )
    result, _ = core.main(args)
    if not result.ok:
        raise RuntimeError(result.detail or 'TierMaker extraction failed')


def _run_generate(json_path, output_path, resolution):
    args = types.SimpleNamespace(
        command='generate', fromPath=str(json_path), toPath=str(output_path),
        reso=resolution,
    )
    result, _ = core.main(args)
    if not result.ok:
        raise RuntimeError(result.detail or 'Tierlist rendering failed')


def process_image(image_path, title=None, resolution=None, magick_cmd=None):
    """Stage all outputs, then replace this image's previous outputs."""
    image_path = pathlib.Path(image_path)
    paths = output_paths(image_path)
    if magick_cmd is None:
        magick_cmd = find_imagemagick()
        if magick_cmd is None:
            raise RuntimeError('ImageMagick was not found on PATH')
    root = image_path.parent / 'tiermaker'
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as temp_dir:
        temp_root = pathlib.Path(temp_dir)
        staged = {kind: temp_root / path.name for kind, path in paths.items()}
        _run_extract(image_path, staged['json'], title or image_path.stem)
        _run_generate(staged['json'], staged['svg'], resolution)
        _run_generate(staged['json'], staged['png'], resolution)
        convert_png_to_jpg(staged['png'], staged['jpg'], magick_cmd)
        for kind, destination in paths.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged[kind].replace(destination)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Create Common Classes tierlists from TierMaker images.')
    parser.add_argument('input_path', help='TierMaker image or folder of images')
    parser.add_argument('--title', help='Document title for a single image')
    parser.add_argument('--reso', help='PNG resolution in WIDTHxHEIGHT format')
    args = parser.parse_args(argv)

    try:
        images = input_images(args.input_path)
        if args.title is not None and not args.title.strip():
            raise ValueError('--title must not be blank')
        if args.title and len(images) != 1:
            raise ValueError('--title can only be used with one image')
        render.parse_resolution(args.reso)
    except ValueError as exc:
        parser.error(str(exc))
    magick_cmd = find_imagemagick()
    if magick_cmd is None:
        parser.error('ImageMagick was not found on PATH; install it first')

    failures = []
    for image_path in images:
        print(f'Processing {image_path.name}...')
        try:
            paths = process_image(image_path, args.title, args.reso, magick_cmd)
        except Exception as exc:  # Keep processing the remaining images.
            failures.append((image_path.name, exc))
            print(f'  FAILED: {exc}', file=sys.stderr)
            continue
        for kind, path in paths.items():
            print(f'  {kind.upper()}: {path}')

    print(f'Processed {len(images) - len(failures)}/{len(images)} image(s).')
    if failures:
        print('Failed images:', file=sys.stderr)
        for name, error in failures:
            print(f'  {name}: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
