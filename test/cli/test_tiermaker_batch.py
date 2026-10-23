import importlib.util
import pathlib

import pytest


_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    'tiermaker_batch', _ROOT / 'ci' / 'tiermaker.py')
_BATCH = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BATCH)


def test_input_images_accepts_one_image_or_a_folder(tmp_path):
    first = tmp_path / 'a.png'
    second = tmp_path / 'b.jpg'
    first.write_bytes(b'')
    second.write_bytes(b'')
    (tmp_path / 'notes.txt').write_text('ignore')

    assert _BATCH.input_images(first) == [first]
    assert _BATCH.input_images(tmp_path) == [first, second]


def test_process_image_preserves_title_and_writes_all_formats(tmp_path, monkeypatch):
    image_path = tmp_path / 'tier.png'
    image_path.write_bytes(b'input')
    calls = []

    def fake_extract(source, json_path, title):
        calls.append(('extract', source, title))
        json_path.write_text('{"title":"October 2026 A"}')

    def fake_generate(json_path, output_path, resolution):
        calls.append(('generate', output_path.suffix, resolution))
        output_path.write_bytes(b'image')

    def fake_jpg(png_path, jpg_path, magick_cmd):
        calls.append(('jpg', magick_cmd))
        jpg_path.write_bytes(b'jpeg')

    monkeypatch.setattr(_BATCH, '_run_extract', fake_extract)
    monkeypatch.setattr(_BATCH, '_run_generate', fake_generate)
    monkeypatch.setattr(_BATCH, 'convert_png_to_jpg', fake_jpg)

    paths = _BATCH.process_image(
        image_path, 'October 2026 A', '1024x768', ['magick'])

    assert paths == {
        'json': tmp_path / 'tiermaker/json/tier.json',
        'svg': tmp_path / 'tiermaker/svg/tier.svg',
        'png': tmp_path / 'tiermaker/png/tier.png',
        'jpg': tmp_path / 'tiermaker/png/jpg/tier.jpg',
    }
    assert all(path.is_file() for path in paths.values())
    assert calls == [
        ('extract', image_path, 'October 2026 A'),
        ('generate', '.svg', '1024x768'),
        ('generate', '.png', '1024x768'),
        ('jpg', ['magick']),
    ]


def test_folder_requires_individual_titles(tmp_path, monkeypatch):
    (tmp_path / 'a.png').write_bytes(b'')
    (tmp_path / 'b.png').write_bytes(b'')
    monkeypatch.setattr(_BATCH, 'find_imagemagick', lambda: ['magick'])

    with pytest.raises(SystemExit, match='2'):
        _BATCH.main([str(tmp_path), '--title', 'one title'])
