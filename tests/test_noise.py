"""
Тесты всех шумов.
"""

from __future__ import annotations
import pytest

from arbacc.core import get


@pytest.fixture
def zeta_stream(ctx):
    """Чистый zeta(3) Stream — база для тестов шумов."""
    Cls = get("series", "zeta")
    z = Cls(params={"s": 3})
    return z.build_stream(ctx)


def test_none_preserves(zeta_stream, ctx):
    """none: значения не меняются."""
    Cls = get("noise", "none")
    n = Cls(params={}, seed=0)
    noisy = n.wrap(zeta_stream, ctx)
    b = ctx.backend
    for i in range(5):
        assert b.digits_of(noisy.get(i), zeta_stream.get(i), 50) >= 48


@pytest.mark.parametrize("sigma", ["1e-3", "1e-6", "1e-10"])
@pytest.mark.parametrize("mode", ["absolute", "relative"])
@pytest.mark.parametrize("seed", [0, 42, 12345])
def test_gaussian_determinism(sigma, mode, seed, zeta_stream, ctx):
    """gaussian: значение a_0 не меняется при досоздании."""
    Cls = get("noise", "gaussian")
    n = Cls(params={"sigma": sigma, "mode": mode}, seed=seed)
    noisy = n.wrap(zeta_stream, ctx)
    b = ctx.backend
    v0_before = noisy.get(0)
    noisy.extend_to(50)
    v0_after = noisy.get(0)
    assert b.digits_of(v0_before, v0_after, 50) >= 48


@pytest.mark.parametrize("phi", ["0.3", "0.5", "0.7", "0.9", "-0.5"])
def test_ar1_forward_only(phi, zeta_stream, ctx):
    """ar1: запрет доступа в прошлое и повторного wrap."""
    Cls = get("noise", "ar1")
    n = Cls(params={"phi": phi, "sigma": "1e-6"}, seed=42)
    noisy = n.wrap(zeta_stream, ctx)
    for i in range(20):
        _ = noisy.get(i)

    # Доступ в прошлое через transform.
    n2 = Cls(params={"phi": phi, "sigma": "1e-6"}, seed=42)
    _ = n2.transform(10, ctx.number("1.0"), ctx)
    with pytest.raises(RuntimeError):
        _ = n2.transform(5, ctx.number("1.0"), ctx)


def test_ar1_double_wrap(zeta_stream, ctx):
    """ar1: повторный wrap одного инстанса → RuntimeError."""
    Cls = get("noise", "ar1")
    n = Cls(params={"phi": "0.5", "sigma": "1e-6"}, seed=42)
    _ = n.wrap(zeta_stream, ctx)
    with pytest.raises(RuntimeError):
        _ = n.wrap(zeta_stream, ctx)