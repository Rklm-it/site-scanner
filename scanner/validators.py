"""Валидация ИНН и ОГРН по контрольным суммам.

Нужна, чтобы не тащить в лиды случайные 10–15-значные числа со страницы.
Алгоритмы — стандартные (ФНС).
"""

from __future__ import annotations

_INN10_WEIGHTS = [2, 4, 10, 3, 5, 9, 4, 6, 8]
_INN12_WEIGHTS_1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
_INN12_WEIGHTS_2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]


def _checksum(digits: list[int], weights: list[int]) -> int:
    return (sum(d * w for d, w in zip(digits, weights)) % 11) % 10


def validate_inn(value: str) -> bool:
    """True, если ИНН (10 или 12 цифр) проходит проверку контрольных цифр."""
    if not value or not value.isdigit():
        return False
    d = [int(c) for c in value]
    if len(d) == 10:
        return _checksum(d[:9], _INN10_WEIGHTS) == d[9]
    if len(d) == 12:
        return (
            _checksum(d[:10], _INN12_WEIGHTS_1) == d[10]
            and _checksum(d[:11], _INN12_WEIGHTS_2) == d[11]
        )
    return False


def validate_ogrn(value: str) -> bool:
    """True, если ОГРН (13) или ОГРНИП (15) проходит проверку.

    ОГРН(13): int(первые 12) % 11 % 10 == 13-я цифра.
    ОГРНИП(15): int(первые 14) % 13 % 10 == 15-я цифра.
    """
    if not value or not value.isdigit():
        return False
    if len(value) == 13:
        return int(value[:12]) % 11 % 10 == int(value[12])
    if len(value) == 15:
        return int(value[:14]) % 13 % 10 == int(value[14])
    return False
