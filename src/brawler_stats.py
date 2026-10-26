"""Validation and derived combat statistics for brawler attacks."""

import decimal
import math


ALLOWED_SHAPES = frozenset(('singleShot', 'multiShot', 'scattered'))
_REQUIRED_FIELDS = ('baseDamage', 'projectiles', 'ammo', 'shape',
                    'reloadSeconds')
_NUMERIC_TYPES = (int, float, decimal.Decimal)


def validate_attack(attack):
    """Validate an attack specification, raising ``ValueError`` if invalid."""
    if not isinstance(attack, dict):
        raise ValueError('attack must be a dictionary')

    missing = [field for field in _REQUIRED_FIELDS if field not in attack]
    if missing:
        raise ValueError(f'missing attack fields: {", ".join(missing)}')

    _validate_numeric_field(attack['baseDamage'], 'baseDamage', minimum=0)
    _validate_integer_field(attack['projectiles'], 'projectiles')
    _validate_integer_field(attack['ammo'], 'ammo')
    _validate_numeric_field(attack['reloadSeconds'], 'reloadSeconds', minimum=0,
                            strictly_positive=True)

    list_lengths = [
        len(attack[field])
        for field in ('baseDamage', 'projectiles', 'ammo')
        if isinstance(attack[field], list)
    ]
    if list_lengths and any(length == 0 for length in list_lengths):
        raise ValueError('list-valued attack fields must not be empty')
    if list_lengths and any(length != list_lengths[0] for length in list_lengths):
        raise ValueError('list-valued attack fields must have matching lengths')

    _validate_shape(attack['shape'], list_lengths[0] if list_lengths else None)


def calculate_damage(base_damage, projectiles):
    """Return per-shot damage, supporting scalar/list broadcasting."""
    base_values, projectiles_values, is_list = _broadcast_pair(
        base_damage, projectiles, 'baseDamage', 'projectiles')
    _validate_numeric_field(base_values, 'baseDamage', minimum=0)
    _validate_integer_field(projectiles_values, 'projectiles')
    damages = [
        _number_from_decimal(_to_decimal(base) * _to_decimal(projectiles))
        for base, projectiles in zip(base_values, projectiles_values)
    ]
    return damages if is_list else damages[0]


def calculate_dps(damage, reload_seconds, duration_seconds=None):
    """Return integer DPS using deterministic positive half-up rounding."""
    damage_values = damage if isinstance(damage, list) else [damage]
    is_list = isinstance(damage, list)
    _validate_numeric_field(damage_values, 'damage', minimum=0)
    _validate_numeric_field(reload_seconds, 'reloadSeconds', minimum=0,
                            strictly_positive=True)
    denominator = reload_seconds if duration_seconds is None else duration_seconds
    _validate_numeric_field(denominator, 'durationSeconds', minimum=0,
                            strictly_positive=True)

    dps_values = [
        _rounded_positive_ratio(
            _to_decimal(damage_value),
            denominator,
        )
        for damage_value in damage_values
    ]
    return dps_values if is_list else dps_values[0]


def calculate_attack_stats(attack):
    """Validate an attack and return its derived damage and integer DPS.

    The result contains ``damage`` and ``dps``.  Each is scalar when all of
    ``baseDamage``, ``projectiles``, and ``ammo`` are scalar, otherwise each is
    a list aligned to the list-valued attack fields.
    """
    validate_attack(attack)
    damage = calculate_damage(attack['baseDamage'], attack['projectiles'])
    dps = calculate_dps(
        damage,
        attack['reloadSeconds'],
        attack.get('durationSeconds'),
    )
    return {'damage': damage, 'dps': dps}


def _broadcast_pair(left, right, left_name, right_name):
    left_is_list = isinstance(left, list)
    right_is_list = isinstance(right, list)
    if not left_is_list and not right_is_list:
        return [left], [right], False
    if left_is_list and not left:
        raise ValueError(f'{left_name} must not be an empty list')
    if right_is_list and not right:
        raise ValueError(f'{right_name} must not be an empty list')
    if left_is_list and right_is_list and len(left) != len(right):
        raise ValueError(f'{left_name} and {right_name} lists must have matching lengths')

    length = len(left) if left_is_list else len(right)
    left_values = left if left_is_list else [left] * length
    right_values = right if right_is_list else [right] * length
    return left_values, right_values, True


def _validate_numeric_field(value, name, minimum=None, strictly_positive=False):
    values = value if isinstance(value, list) else [value]
    for item in values:
        if isinstance(item, bool) or not isinstance(item, _NUMERIC_TYPES):
            raise ValueError(f'{name} must contain numeric values')
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError(f'{name} must contain finite numeric values')
        if isinstance(item, decimal.Decimal) and not item.is_finite():
            raise ValueError(f'{name} must contain finite numeric values')
        if strictly_positive and item <= 0:
            raise ValueError(f'{name} must be positive')
        if minimum is not None and item < minimum:
            raise ValueError(f'{name} must be at least {minimum}')


def _validate_integer_field(value, name):
    values = value if isinstance(value, list) else [value]
    for item in values:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ValueError(f'{name} must contain positive integers')


def _validate_shape(value, expected_length):
    if isinstance(value, list):
        if expected_length is None:
            raise ValueError('a list-valued shape requires list-valued attack fields')
        if len(value) != expected_length:
            raise ValueError('shape list must match the attack list length')
        shapes = value
    else:
        shapes = [value]
    for shape in shapes:
        if shape not in ALLOWED_SHAPES:
            raise ValueError(f'unsupported shape: {shape!r}')


def _to_decimal(value):
    if isinstance(value, decimal.Decimal):
        return value
    return decimal.Decimal(str(value))


def _number_from_decimal(value):
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _rounded_positive_ratio(numerator, denominator):
    with decimal.localcontext() as context:
        context.prec = 50
        ratio = _to_decimal(numerator) / _to_decimal(denominator)
        return int(ratio.quantize(decimal.Decimal('1'), rounding=decimal.ROUND_HALF_UP))
