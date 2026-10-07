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


def test_output_paths_use_input_subdirectories(tmp_path):
    paths = _BATCH.output_paths(tmp_path, tmp_path / 'tier.png')

    assert paths == {
        'json': tmp_path / 'json' / 'tier.json',
    }


def test_image_output_paths_use_lowercase_mode_map_stem(tmp_path):
    paths = _BATCH.image_output_paths(
        tmp_path, 'brawlBall', 'pinballDreams')

    assert paths == {
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

    monkeypatch.setattr(_BATCH, '_run_extract', fake_extract)
    monkeypatch.setattr(_BATCH, '_run_generate', lambda *args: None)
    monkeypatch.setattr(
        _BATCH, 'find_map_image', lambda _map_name: map_path)

    paths = _BATCH.process_image(image_path, tmp_path)

    assert paths['svg'] == tmp_path / 'svg' / 'brawlball-pinballdreams.svg'
    assert paths['png'] == tmp_path / 'png' / 'brawlball-pinballdreams.png'
    assert paths['org'] == tmp_path / 'org' / 'brawlball-pinballdreams.png'
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

    _BATCH.process_image(first_image, tmp_path)
    with pytest.raises(FileExistsError, match='same stitched output'):
        _BATCH.process_image(second_image, tmp_path)


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