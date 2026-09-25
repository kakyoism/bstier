import importlib.util
import pathlib

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
        'svg': tmp_path / 'svg' / 'tier.svg',
        'png': tmp_path / 'png' / 'tier.png',
    }


def test_clear_outputs_removes_stale_files_and_preserves_inputs(tmp_path):
    input_image = tmp_path / 'tier.png'
    input_image.write_bytes(b'input')
    for name in ('json', 'svg', 'png'):
        output_dir = tmp_path / name
        output_dir.mkdir()
        (output_dir / 'stale.output').write_text('stale')

    _BATCH.clear_outputs(tmp_path)

    assert input_image.read_bytes() == b'input'
    for name in ('json', 'svg', 'png'):
        output_dir = tmp_path / name
        assert output_dir.is_dir()
        assert list(output_dir.iterdir()) == []