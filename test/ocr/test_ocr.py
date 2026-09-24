import pathlib
import sys
import types

import pytest


_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / 'src'))

import ocr


def test_tesseract_adapter_returns_stdout(monkeypatch):
    calls = []

    def fake_run(command, check, capture_output, text):
        calls.append((command, check, capture_output, text))
        return types.SimpleNamespace(
            returncode=0,
            stdout='Brawi Stars Tier List — Pinball Dreams\n',
            stderr='',
        )

    monkeypatch.setattr(ocr.subprocess, 'run', fake_run)

    adapter = ocr.TesseractMapTitleAdapter()

    assert adapter('/tmp/tierlist.png') == 'Brawi Stars Tier List — Pinball Dreams'
    assert calls == [(
        ['tesseract', '/tmp/tierlist.png', 'stdout', '--psm', '6'],
        False,
        True,
        True,
    )]


@pytest.mark.parametrize('failure, expected', [
    (
        types.SimpleNamespace(returncode=1, stdout='', stderr='bad image'),
        RuntimeError,
    ),
    (
        types.SimpleNamespace(returncode=0, stdout='   ', stderr=''),
        ValueError,
    ),
])
def test_tesseract_adapter_rejects_failed_or_empty_output(
        monkeypatch, failure, expected):
    monkeypatch.setattr(ocr.subprocess, 'run', lambda *args, **kwargs: failure)

    with pytest.raises(expected):
        ocr.TesseractMapTitleAdapter()('/tmp/tierlist.png')


def test_tesseract_adapter_reports_missing_executable(monkeypatch):
    def missing_executable(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(ocr.subprocess, 'run', missing_executable)

    with pytest.raises(RuntimeError, match='Unable to execute OCR backend'):
        ocr.TesseractMapTitleAdapter()('/tmp/tierlist.png')