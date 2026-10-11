"""
Метрики: digits_gained возвращает осмысленные числа.
"""

from __future__ import annotations
import pytest

from arbacc.runner.metrics import digits_gained


@pytest.mark.parametrize("d_expected,value,exact", [
    (20, "1." + "0" * 19 + "1", "1." + "0" * 20),
    (4, "1.0000999999999", "1.0"),
    (50, "1.0", "1.0"),
])
def test_digits_gained_known(d_expected, value, exact, ctx):
    """digits_gained возвращает ожидаемое число на известных данных."""
    d = digits_gained(ctx.number(value), ctx.number(exact), ctx)
    assert abs(d - d_expected) <= 2, f"got {d}, expected ~{d_expected}"