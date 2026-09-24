import json
import pathlib
import sys

import kkpyutil as util


_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / 'src'))

import m1


_MAP_PATH = _ROOT / 'res/spec/all.map.json'
_BRAWLER_PATH = _ROOT / 'res/spec/all.brawler.json'
_FIXTURE_PATH = _ROOT / 'test/extract/_ref/bstier.json'


def test_normalize_map_name_keeps_ocr_separate_from_canonicalization():
    map_catalog = util.load_json(_MAP_PATH)

    assert m1.normalize_map_name(
        'Brawl Stars Tier List —- Pinball Dreams\nExported on 2026-09-03',
        map_catalog,
    ) == 'pinballDreams'


def test_normalize_role_label_only_handles_unknown_values():
    assert m1.normalize_role_label('') == '*'
    assert m1.normalize_role_label('antiAggro') == 'antiAggro'
    assert m1.normalize_role_label('safeDamage') == 'safeDamage'


def test_build_master_document_preserves_source_order_inside_sorted_groups():
    tierlist = json.loads(_FIXTURE_PATH.read_text(encoding='utf-8'))
    global_roles = m1.load_global_roles(_BRAWLER_PATH)
    mode_roles = m1.load_mode_roles(_BRAWLER_PATH)

    document = m1.build_master_document(
        tierlist,
        'pinballDreams',
        'brawlBall',
        global_roles,
        mode_roles,
    )

    assert list(document['globalRoles']) == [
        'aggro', 'antiTank', 'controller', 'sniper', 'support', 'tank', 'thrower'
    ]
    assert document['globalRoles']['sniper'] == [
        'Gus', 'Pierce', 'Najia', 'Byron', 'Brock', 'Piper', 'Bonnie',
        'Bea', 'Belle', 'Darryl', 'Mandy', 'Nani', 'Rt',
    ]
    assert document['originalTierlist'] == tierlist
    assert document['map'] == 'pinballDreams'
    assert document['mode'] == 'brawlBall'
    assert '*' in document['mapRoles']