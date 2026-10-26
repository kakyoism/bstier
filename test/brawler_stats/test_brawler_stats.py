import json
import pathlib
import sys

import pytest


_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / 'src'))

import brawler_stats


def test_brawler_spec_uses_derived_combat_schema():
    data = json.loads((_ROOT / 'res/spec/all.brawler.json').read_text())
    records = [spec for name, spec in data.items() if name != 'version']

    assert len(records) == 108
    for spec in records:
        assert 'reloadSeconds' not in spec
        assert 'speedUnits' in spec
        assert 'reloadSpeedSeconds' not in spec
        assert 'movementSpeedUnits' not in spec
        assert 'DPS' not in spec
        attack = spec['mainAttack']
        assert 'reloadSeconds' in attack
        assert list(attack).index('reloadSeconds') == list(attack).index('range') + 1
        assert isinstance(attack['ammo'], int)
        brawler_stats.validate_attack(attack)
        derived = brawler_stats.calculate_attack_stats(attack)
        assert attack['damage'] == derived['damage']
        # Catalog DPS can account for attack-specific behavior beyond the
        # helper's generic damage / reload calculation.
        if 'durationSeconds' in attack:
            assert attack['durationSeconds'] > 0


def test_scalar_attack_stats():
    attack = {
        'baseDamage': 40,
        'projectiles': 3,
        'ammo': 2,
        'reloadSeconds': 1.2,
        'shape': 'multiShot',
    }

    assert brawler_stats.calculate_attack_stats(attack) == {
        'damage': 120,
        'dps': 100,
    }


def test_array_attack_stats_are_aligned():
    attack = {
        'baseDamage': [10, 20],
        'projectiles': [2, 3],
        'ammo': [3, 1],
        'reloadSeconds': 2,
        'shape': ['multiShot', 'multiShot'],
    }

    assert brawler_stats.calculate_attack_stats(attack) == {
        'damage': [20, 60],
        'dps': [10, 30],
    }


def test_scalar_values_broadcast_to_arrays():
    assert brawler_stats.calculate_attack_stats({
        'baseDamage': [10, 20],
        'projectiles': 2,
        'ammo': 3,
        'reloadSeconds': 2,
        'shape': ['singleShot', 'singleShot'],
    }) == {'damage': [20, 40], 'dps': [10, 20]}


def test_dps_uses_positive_half_up_rounding():
    assert brawler_stats.calculate_dps(5, 2) == 3
    assert brawler_stats.calculate_dps([1, 3], 2) == [1, 2]


def test_continuous_attack_uses_duration_instead_of_reload_tick():
    attack = {
        'baseDamage': 420,
        'projectiles': 40,
        'ammo': 3,
        'shape': 'multiShot',
        'durationSeconds': 6,
        'reloadSeconds': 0.2,
    }

    assert brawler_stats.calculate_attack_stats(attack) == {
        'damage': 16800,
        'dps': 2800,
    }


@pytest.mark.parametrize('field, value', [
    ('reloadSeconds', 0),
    ('reloadSeconds', -1),
    ('ammo', 0),
    ('ammo', 2.0),
    ('projectiles', [1, 0]),
    ('baseDamage', -1),
    ('baseDamage', '100'),
])
def test_invalid_values_raise_value_error(field, value):
    attack = {
        'baseDamage': 100,
        'projectiles': 1,
        'ammo': 1,
        'reloadSeconds': 1,
        'shape': 'singleShot',
    }
    attack[field] = value

    with pytest.raises(ValueError):
        brawler_stats.validate_attack(attack)


def test_mismatched_lists_raise_value_error():
    attack = {
        'baseDamage': [10, 20],
        'projectiles': [1],
        'ammo': 1,
        'reloadSeconds': 1,
        'shape': ['singleShot', 'singleShot'],
    }

    with pytest.raises(ValueError):
        brawler_stats.calculate_attack_stats(attack)


def test_shapes_are_validated_and_can_align_to_arrays():
    attack = {
        'baseDamage': [10, 20],
        'projectiles': 1,
        'ammo': 1,
        'reloadSeconds': 1,
        'shape': ['singleShot', 'scattered'],
    }

    assert brawler_stats.calculate_attack_stats(attack) == {
        'damage': [10, 20],
        'dps': [10, 20],
    }


@pytest.mark.parametrize('shape', [
    'cone',
    ['singleShot', 'multiShot', 'scattered'],
])
def test_invalid_shapes_raise_value_error(shape):
    attack = {
        'baseDamage': [10, 20],
        'projectiles': 1,
        'ammo': 1,
        'reloadSeconds': 1,
        'shape': shape,
    }

    with pytest.raises(ValueError):
        brawler_stats.validate_attack(attack)


def test_brawler_catalog_keys_are_sorted_after_version():
    data = json.loads((_ROOT / 'res/spec/all.brawler.json').read_text())
    keys = [name for name in data if name != 'version']

    assert list(data)[0] == 'version'
    assert keys == sorted(keys, key=str.casefold)


def test_brawler_catalog_marks_waterborne_brawlers():
    data = json.loads((_ROOT / 'res/spec/all.brawler.json').read_text())
    expected = {'alli', 'angelo', 'eve', 'juju', 'r-t', 'shade', 'wendy'}

    assert all(isinstance(spec['waterborne'], bool)
               for name, spec in data.items() if name != 'version')
    assert {
        name for name, spec in data.items()
        if name != 'version' and spec['waterborne']
    } == expected
