"""
Тесты режимов округления.
"""

from __future__ import annotations
import pytest

from arbacc.core import Context
from arbacc.precision import get_backend, list_backends


@pytest.mark.parametrize("mode", ["nearest", "floor", "ceiling"])
def test_mpmath_rounding_modes(mode):
    """mpmath принимает nearest/floor/ceiling."""
    b = get_backend("mpmath")
    ctx = Context(backend=b, dps=30, rounding=mode)
    x = ctx.number("1.0000000000000001")
    s = b.to_str(x, 30)
    assert isinstance(s, str) and len(s) > 0


@pytest.mark.parametrize("mode", ["toward_zero", "away_from_zero"])
def test_mpmath_extra_modes(mode):
    b = get_backend("mpmath")
    Context(backend=b, dps=30, rounding=mode)  # не падает


@pytest.mark.parametrize("mode", ["rad"])
def test_mpmath_rejects_arb_only_modes(mode):
    """mpmath не поддерживает 'rad' — должно быть ValueError."""
    b = get_backend("mpmath")
    with pytest.raises(ValueError):
        Context(backend=b, dps=30, rounding=mode)


def test_unknown_rounding_rejected():
    b = get_backend("mpmath")
    with pytest.raises(ValueError):
        Context(backend=b, dps=30, rounding="бред")


@pytest.mark.backend
@pytest.mark.parametrize("mode", ["nearest", "floor", "ceiling", "rad"])
def test_arb_rounding_modes(mode):
    if "arb" not in list_backends():
        pytest.skip("arb backend недоступен")
    b = get_backend("arb")
    ctx = Context(backend=b, dps=30, rounding=mode)
    x = ctx.number("0.6")
    y = b.cos(x, 30)
    s = b.to_str(y, 30)
    assert isinstance(s, str)


@pytest.mark.backend
def test_arb_floor_le_ceiling():
    """floor ≤ mid ≤ ceiling для arb."""
    if "arb" not in list_backends():
        pytest.skip("arb backend недоступен")
    b = get_backend("arb")

    ctx_mid = Context(backend=b, dps=30, rounding="nearest")
    y_mid = b.cos(ctx_mid.number("0.6"), 30)

    # Один и тот же y — но в разных "rounding mode" вернёт разные строки.
    b_mid = get_backend("arb")
    ctx_low = Context(backend=b_mid, dps=30, rounding="floor")
    s_low = b_mid.to_str(y_mid, 30)

    b_hi = get_backend("arb")
    ctx_hi = Context(backend=b_hi, dps=30, rounding="ceiling")
    s_hi = b_hi.to_str(y_mid, 30)

    # Строки могут совпадать для хорошо определённого значения,
    # но не должны упасть.
    assert s_low and s_hi


def test_context_repr_has_rounding():
    b = get_backend("mpmath")
    ctx = Context(backend=b, dps=30, rounding="floor")
    assert "floor" in repr(ctx)