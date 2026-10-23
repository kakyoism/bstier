import json
import pathlib
import sys

import kkpyutil as util
import pytest


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


def test_normalize_map_name_resolves_hot_potato_and_ring_of_fire():
    map_catalog = util.load_json(_MAP_PATH)

    assert m1.normalize_map_name(
        'Brawl Stars Tier List — Hot Potato', map_catalog) == 'hotPotato'
    assert m1.normalize_map_name(
        'Brawl Stars Tier List — Ring of Fire', map_catalog) == 'ringOfFire'


def test_resolve_map_context_normalizes_map_and_tags():
    map_catalog = util.load_json(_MAP_PATH)

    assert m1.resolve_map_context('Pinball Dreams', map_catalog) == {
        'map': 'pinballDreams',
        'mode': 'brawlBall',
        'tags': ['closed'],
    }
    assert m1.resolve_map_context('hideout', map_catalog)['tags'] == ['open']


def test_resolve_map_context_rejects_unknown_or_unsupported_maps():
    with pytest.raises(KeyError):
        m1.resolve_map_context('not-a-map', {'version': 1})

    with pytest.raises(ValueError):
        m1.resolve_map_context('testMap', {
            'version': 1,
            'testMap': {'mode': 'unsupported', 'tags': []},
        })


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
        'gus', 'pierce', 'najia', 'byron', 'brock', 'piper', 'bonnie',
        'bea', 'angelo', 'belle', 'mandy', 'nani', 'r-t',
    ]
    assert document['originalTierlist'] == tierlist
    assert document['map'] == 'pinballDreams'
    assert document['mode'] == 'brawlBall'
    assert '*' not in document['mapRoles']


def test_global_document_preserves_tier_ranking_within_each_class():
    document = m1.build_global_document(
        {'S': ['gus', 'piper'], 'A': ['brock', 'bull'], 'B': ['belle']},
        'October 2026 A',
        {'gus': 'sniper', 'piper': 'sniper', 'brock': 'sniper',
         'bull': 'tank', 'belle': 'sniper'},
    )

    assert document['globalRoles']['sniper'] == [
        'gus', 'piper', 'brock', 'belle']


def test_build_master_document_from_ocr_uses_injected_adapter():
    tierlist = {'S': ['gus', 'bull']}
    map_catalog = util.load_json(_MAP_PATH)
    global_roles = m1.load_global_roles(_BRAWLER_PATH)
    mode_roles = m1.load_mode_roles(_BRAWLER_PATH)
    calls = []

    def fake_ocr(image_path):
        calls.append(image_path)
        return 'Brawl Stars Tier List —- Pinball Dreams\nExported on 2026-09-03'

    document = m1.build_master_document_from_ocr(
        tierlist,
        '/tmp/deepdraft.png',
        fake_ocr,
        map_catalog,
        global_roles,
        mode_roles,
    )

    assert calls == ['/tmp/deepdraft.png']
    assert document['map'] == 'pinballDreams'
    assert document['mode'] == 'brawlBall'
    assert document['originalTierlist'] == tierlist
