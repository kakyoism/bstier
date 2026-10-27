import json
import pathlib
import sys

import pytest


_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / 'src'))

import stats


def _spec(health, main_range, super_range, speed, reload_seconds,
          role='sniper', main_rating='LONG', super_rating='LONG',
          speed_rating='NORMAL', reload_rating='NORMAL'):
    return {
        'health': health,
        'mainAttack': {'range': main_range,
                       'reloadSeconds': reload_seconds},
        'super': {'range': super_range},
        'speedUnits': speed,
        'rating': {
            'rangeMain': main_rating, 'rangeSuper': super_rating,
            'speed': speed_rating, 'reload': reload_rating,
        },
        'roles': {'*': role},
    }


def test_health_bands_and_numeric_order():
    catalog = {
        'low': _spec(4999, 4, 4, 700, 1.5),
        'five': _spec(5000, 4, 4, 700, 1.5),
        'high': _spec(10000, 4, 4, 700, 1.5),
        'higher': _spec(13000, 4, 4, 700, 1.5),
    }

    document = stats.build_document(catalog, stats.STATS[0])

    assert document['originalTierlist'] == {
        '10000+': ['higher', 'high'],
        '5000': ['five'],
        '5000-': ['low'],
    }
    assert document['globalRoles']['sniper'] == [
        'higher', 'high', 'five', 'low']


def test_slash_rating_uses_first_label_and_na_stays_last():
    catalog = {
        'split': _spec(8000, 9, 4, 700, 1.5,
                       main_rating='LONG/NORMAL', super_rating='N/A'),
        'plain': _spec(8000, 10, 8, 700, 1.5,
                       super_rating='LONG'),
    }
    main = stats.build_document(catalog, stats.STATS[1])
    super_range = stats.build_document(catalog, stats.STATS[2])

    assert main['originalTierlist']['LONG'] == ['plain', 'split']
    assert super_range['originalTierlist'] == {
        'LONG': ['plain'], 'N/A': ['split']}
    assert super_range['globalRoles']['sniper'] == ['plain', 'split']


def test_range_charts_use_maximum_of_multiple_ranges():
    catalog = {
        'multi': _spec(8000, [2.7, 9.0], [4, 10.3], 700, 1.5),
        'single': _spec(8000, 8.0, 9.0, 700, 1.5),
    }

    main = stats.build_document(catalog, stats.STATS[1])
    super_range = stats.build_document(catalog, stats.STATS[2])

    assert main['values'] == {'multi': 9.0, 'single': 8.0}
    assert main['originalTierlist']['LONG'] == ['multi', 'single']
    assert main['globalRoles']['sniper'] == ['multi', 'single']
    assert super_range['values'] == {'multi': 10.3, 'single': 9.0}
    assert super_range['globalRoles']['sniper'] == ['multi', 'single']


@pytest.mark.parametrize('ranges', [[], [8.0, None], [8.0, True]])
def test_range_charts_reject_invalid_range_lists(ranges):
    catalog = {'bad': _spec(8000, ranges, 9.0, 700, 1.5)}

    with pytest.raises(ValueError, match='values|numeric'):
        stats.build_document(catalog, stats.STATS[1])


def test_common_classes_prioritize_rating_before_numeric_range():
    catalog = {
        'carl': _spec(8000, 8.33, 3, 720, 2.0,
                      role='aggro', main_rating='LONG'),
        'shade': _spec(8000, 9.0, 8.67, 820, 0.8,
                       role='aggro', main_rating='SHORT'),
        'longer': _spec(8000, 10.0, 3, 720, 2.0,
                        role='aggro', main_rating='LONG'),
    }

    document = stats.build_document(catalog, stats.STATS[1])

    assert document['globalRoles']['aggro'] == ['longer', 'carl', 'shade']
    assert document['originalTierlist']['LONG'] == ['longer', 'carl']


def test_reload_speed_inverts_seconds_and_keeps_fastest_left():
    catalog = {
        'slow': _spec(8000, 4, 4, 700, 2.0,
                      reload_rating='SLOW'),
        'fast': _spec(8000, 4, 4, 700, 0.5,
                      reload_rating='VERY FAST'),
    }
    document = stats.build_document(catalog, stats.STATS[4])

    assert document['values'] == {'slow': 0.5, 'fast': 2.0}
    assert document['globalRoles']['sniper'] == ['fast', 'slow']
    assert document['originalTierlist']['VERY FAST'] == ['fast']
    assert document['title'] == 'Brawler Tierlist: Reload Speed'


def test_reload_speed_uses_first_value_for_alternate_forms():
    catalog = {
        'bonnie': _spec(10000, 9, 7, 620, [1.0, 2.0],
                        reload_rating='VERY FAST/SLOW'),
    }

    document = stats.build_document(catalog, stats.STATS[4])

    assert document['values']['bonnie'] == 1.0
    assert document['originalTierlist'] == {'VERY FAST': ['bonnie']}


def test_current_catalog_places_every_brawler_in_both_panels():
    catalog = json.loads((_ROOT / 'res/spec/all.brawler.json').read_text())
    names = set(catalog) - {'version'}

    for stat in stats.STATS:
        document = stats.build_document(catalog, stat)
        tier_names = [name for row in document['originalTierlist'].values()
                      for name in row]
        role_names = [name for row in document['globalRoles'].values()
                      for name in row]
        assert set(tier_names) == set(role_names) == names
        assert len(tier_names) == len(role_names) == len(names)


def test_current_catalog_respects_rating_then_value_in_every_class():
    catalog = json.loads((_ROOT / 'res/spec/all.brawler.json').read_text())

    for stat in stats.STATS:
        document = stats.build_document(catalog, stat)
        rating = {
            name: tier for tier, names in document['originalTierlist'].items()
            for name in names
        }
        rank = {tier: index for index, tier in enumerate(stat.tiers)}
        for names in document['globalRoles'].values():
            actual = [(rank[rating[name]], -document['values'][name], name)
                      for name in names]
            assert actual == sorted(actual)
