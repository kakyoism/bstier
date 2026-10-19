import importlib.util
import pathlib

from PIL import Image
import pytest


_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    'deepdraft_batch', _ROOT / 'ci' / 'deepdraft.py')
_BATCH = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BATCH)


def test_discover_images_filters_supported_files_and_sorts(tmp_path):
    (tmp_path / 'z.jpg').write_bytes(b'')
    (tmp_path / 'a.PNG').write_bytes(b'')
    (tmp_path / 'notes.txt').write_text('ignore')

    assert [path.name for path in _BATCH.discover_images(tmp_path)] == [
        'a.PNG', 'z.jpg']


def test_discover_images_rejects_duplicate_basenames(tmp_path):
    (tmp_path / 'tier.png').write_bytes(b'')
    (tmp_path / 'tier.jpg').write_bytes(b'')

    with pytest.raises(ValueError, match='unique basenames'):
        _BATCH.discover_images(tmp_path)


def test_image_output_paths_use_lowercase_mode_map_stem(tmp_path):
    paths = _BATCH.image_output_paths(
        tmp_path, 'brawlBall', 'pinballDreams')

    assert paths == {
        'json': tmp_path / 'json' / 'brawlball-pinballdreams.json',
        'svg': tmp_path / 'svg' / 'brawlball-pinballdreams.svg',
        'png': tmp_path / 'png' / 'brawlball-pinballdreams.png',
        'org': tmp_path / 'org' / 'brawlball-pinballdreams.png',
    }


def test_stitched_output_path_uses_lowercase_mode_and_map(tmp_path):
    assert _BATCH.stitched_output_path(
        tmp_path, 'brawlBall', 'pinballDreams') == (
            tmp_path / 'org' / 'brawlball-pinballdreams.png')


def test_stitched_output_path_requires_mode_and_map(tmp_path):
    with pytest.raises(ValueError, match='both mode and map'):
        _BATCH.stitched_output_path(tmp_path, None, 'pinballDreams')


def test_find_map_image_matches_normalized_map_name(tmp_path):
    map_path = tmp_path / 'Pinball_Dreams.png'
    map_path.write_bytes(b'map')

    assert _BATCH.find_map_image('pinballDreams', tmp_path) == map_path


def test_transparent_map_pixels_use_fixed_tierlist_background():
    transparent_image = Image.new('RGBA', (1, 1), (0, 0, 255, 0))

    opaque_image = _BATCH._opaque_rgb(transparent_image)

    assert opaque_image.getpixel((0, 0)) == (43, 43, 43)


def test_process_image_stitches_map_left_of_tierlist(tmp_path, monkeypatch):
    image_path = tmp_path / 'raw-tierlist.png'
    map_path = tmp_path / 'Pinball_Dreams.png'
    Image.new('RGB', (4, 2), (255, 0, 0)).save(image_path)
    Image.new('RGB', (1, 1), (0, 0, 255)).save(map_path)

    def fake_extract(_image_path, json_path):
        json_path.write_text(
            '{"map": "pinballDreams", "mode": "brawlBall"}',
            encoding='utf-8',
        )

    conversions = []

    def fake_convert(png_path, jpg_path, magick_cmd):
        conversions.append((png_path, jpg_path, magick_cmd))

    monkeypatch.setattr(_BATCH, '_run_extract', fake_extract)
    monkeypatch.setattr(_BATCH, '_run_generate', lambda *args: None)
    monkeypatch.setattr(
        _BATCH, 'find_map_image', lambda _map_name: map_path)
    monkeypatch.setattr(_BATCH, 'convert_png_to_jpg', fake_convert)

    paths = _BATCH.process_image(
        image_path, tmp_path, magick_cmd=['magick'])

    assert paths['json'] == tmp_path / 'json' / 'brawlball-pinballdreams.json'
    assert paths['json'].is_file()
    assert not (tmp_path / 'json' / 'raw-tierlist.json').exists()
    assert paths['svg'] == tmp_path / 'svg' / 'brawlball-pinballdreams.svg'
    assert paths['png'] == tmp_path / 'png' / 'brawlball-pinballdreams.png'
    assert paths['org'] == tmp_path / 'org' / 'brawlball-pinballdreams.png'
    assert paths['orgJpg'] == (
        tmp_path / 'org' / 'jpg' / 'brawlball-pinballdreams.jpg')
    assert paths['pngJpg'] == (
        tmp_path / 'png' / 'jpg' / 'brawlball-pinballdreams.jpg')
    assert conversions == [
        (paths['org'], paths['orgJpg'], ['magick']),
        (paths['png'], paths['pngJpg'], ['magick']),
    ]
    with Image.open(paths['org']) as stitched:
        assert stitched.format == 'PNG'
        assert stitched.size == (6, 2)
        assert stitched.getpixel((0, 0)) == (0, 0, 255)
        assert stitched.getpixel((2, 0)) == (255, 0, 0)


def test_process_image_rejects_duplicate_mode_map_output(tmp_path, monkeypatch):
    first_image = tmp_path / 'first.png'
    second_image = tmp_path / 'second.png'
    map_path = tmp_path / 'Pinball_Dreams.png'
    Image.new('RGB', (2, 2), (255, 0, 0)).save(first_image)
    Image.new('RGB', (2, 2), (0, 255, 0)).save(second_image)
    Image.new('RGB', (2, 2), (0, 0, 255)).save(map_path)

    def fake_extract(_image_path, json_path):
        json_path.write_text(
            '{"map": "pinballDreams", "mode": "brawlBall"}',
            encoding='utf-8',
        )

    monkeypatch.setattr(_BATCH, '_run_extract', fake_extract)
    monkeypatch.setattr(_BATCH, '_run_generate', lambda *args: None)
    monkeypatch.setattr(
        _BATCH, 'find_map_image', lambda _map_name: map_path)
    monkeypatch.setattr(_BATCH, 'convert_png_to_jpg', lambda *args: None)

    _BATCH.process_image(first_image, tmp_path, magick_cmd=['magick'])
    with pytest.raises(FileExistsError, match='same stitched output'):
        _BATCH.process_image(second_image, tmp_path, magick_cmd=['magick'])
    assert [path.name for path in (tmp_path / 'json').iterdir()] == [
        'brawlball-pinballdreams.json']


def test_clear_outputs_removes_stale_files_and_preserves_inputs(tmp_path):
    input_image = tmp_path / 'tier.png'
    input_image.write_bytes(b'input')
    for name in ('json', 'svg', 'png', 'org'):
        output_dir = tmp_path / name
        output_dir.mkdir()
        (output_dir / 'stale.output').write_text('stale')

    _BATCH.clear_outputs(tmp_path)

    assert input_image.read_bytes() == b'input'
    for name in ('json', 'svg', 'png', 'org'):
        output_dir = tmp_path / name
        assert output_dir.is_dir()
        assert list(output_dir.iterdir()) == []


def test_jpg_output_path_uses_jpg_subfolder(tmp_path):
    png_path = tmp_path / 'org' / 'brawlball-pinballdreams.png'

    assert _BATCH.jpg_output_path(png_path) == (
        tmp_path / 'org' / 'jpg' / 'brawlball-pinballdreams.jpg')


def test_find_imagemagick_prefers_magick(monkeypatch):
    monkeypatch.setattr(
        _BATCH.shutil, 'which', lambda name: f'/bin/{name}')

    assert _BATCH.find_imagemagick() == ['magick']


def test_find_imagemagick_falls_back_to_convert_off_windows(monkeypatch):
    monkeypatch.setattr(
        _BATCH.shutil, 'which',
        lambda name: '/bin/convert' if name == 'convert' else None)
    monkeypatch.setattr(_BATCH.sys, 'platform', 'darwin')

    assert _BATCH.find_imagemagick() == ['convert']


def test_find_imagemagick_ignores_convert_on_windows(monkeypatch):
    monkeypatch.setattr(
        _BATCH.shutil, 'which',
        lambda name: 'C:/convert.exe' if name == 'convert' else None)
    monkeypatch.setattr(_BATCH.sys, 'platform', 'win32')

    assert _BATCH.find_imagemagick() is None


def test_convert_png_to_jpg_builds_flatten_command(tmp_path, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return _BATCH.subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(_BATCH.subprocess, 'run', fake_run)
    png_path = tmp_path / 'a.png'
    jpg_path = tmp_path / 'jpg' / 'a.jpg'

    _BATCH.convert_png_to_jpg(png_path, jpg_path, ['magick'])

    assert jpg_path.parent.is_dir()
    assert calls[0][0] == [
        'magick', str(png_path),
        '-background', '#2b2b2b', '-alpha', 'remove', '-alpha', 'off',
        '-quality', '92', str(jpg_path),
    ]
    assert 'shell' not in calls[0][1]


def test_convert_png_to_jpg_raises_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        _BATCH.subprocess, 'run',
        lambda command, **kwargs: _BATCH.subprocess.CompletedProcess(
            command, 1, '', 'bad input'))

    with pytest.raises(RuntimeError, match='bad input'):
        _BATCH.convert_png_to_jpg(
            tmp_path / 'a.png', tmp_path / 'jpg' / 'a.jpg', ['magick'])


@pytest.mark.skipif(
    _BATCH.find_imagemagick() is None, reason='ImageMagick not installed')
def test_convert_png_to_jpg_flattens_transparency(tmp_path):
    png_path = tmp_path / 'a.png'
    jpg_path = tmp_path / 'jpg' / 'a.jpg'
    Image.new('RGBA', (8, 8), (0, 0, 255, 0)).save(png_path)

    _BATCH.convert_png_to_jpg(png_path, jpg_path, _BATCH.find_imagemagick())

    with Image.open(jpg_path) as converted:
        assert converted.format == 'JPEG'
        red, green, blue = converted.convert('RGB').getpixel((4, 4))
        assert all(abs(value - 43) <= 2 for value in (red, green, blue))
