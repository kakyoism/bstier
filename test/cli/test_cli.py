import pathlib
import sys


_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import src.cli as cli


def test_extract_parser_supports_master_output():
    args = cli.create_parser().parse_args([
        'extract',
        '--source', 'deepdraft',
        '--master',
        '--from', 'input.png',
    ])

    assert args.master is True
    assert args.source == 'deepdraft'


def test_extract_parser_supports_tiermaker_title():
    args = cli.create_parser().parse_args([
        'extract',
        '--source', 'tiermaker',
        '--title', 'June 2026',
        '--from', 'input.jpg',
    ])

    assert args.source == 'tiermaker'
    assert args.title == 'June 2026'