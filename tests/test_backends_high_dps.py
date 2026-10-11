"""
Проверка backend'ов на высоких dps.

Ключевая проверка: arb.digits_of не должна терять цифры при
dps > 300, где |diff| ~ 1e-350 и float() уходит в денормали.
"""

from __future__ import annotations
import pytest

from arbacc.core import Context
from arbacc.precision import get_backend, list_backends


@pytest.mark.backend
@pytest.mark.parametrize("dps", [100, 200, 400])
def test_arb_digits_of_high_dps(dps):
    """arb.digits_of корректен при высоких dps."""
    if "arb" not in list_backends():
        pytest.skip("arb backend недоступен")
    b = get_backend("arb")
    ctx = Context(backend=b, dps=dps)

    a_str = "1." + "0" * (dps - 2) + "1"
    b_str = "1." + "0" * (dps - 1)
    x = ctx.number(a_str)
    y = ctx.number(b_str)
    d = b.digits_of(x, y, dps)
    # Ожидаем dps-1 ± 2.
    assert abs(d - (dps - 1)) <= 2, (
        f"arb dps={dps}: digits_of вернул {d}, ожидалось ~{dps - 1}"
    )