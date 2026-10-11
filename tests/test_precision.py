"""
Тесты backend'ов: арифметика, dps, метрики.
"""

from __future__ import annotations
import math
import pytest

from arbacc.core import Context
from arbacc.precision import get_backend, list_backends


# --- Простые арифметические операции ---------------------------------------

@pytest.mark.parametrize("dps", [10, 20, 50, 100, 200])
def test_roundtrip(dps):
    """Число → строка → число сохраняет dps."""
    b = get_backend("mpmath")
    ctx = Context(backend=b, dps=dps)
    x = ctx.number("1.2345678901234567890123456789")
    s = b.to_str(x, dps)
    y = b.from_str(s, dps)
    d = b.digits_of(x, y, dps)
    assert d >= dps - 2, f"dps={dps}: потеря точности, digits={d}"


def test_add_sub_mul_div(ctx):
    """Арифметика: 3.14 + 2.71 = 5.85 и т.п."""
    b = ctx.backend
    a = ctx.number("3.14")
    c = ctx.number("2.71")

    assert b.sign(b.sub(b.add(a, c, 50), ctx.number("5.85"), 50), 50) == 0
    assert b.sign(b.sub(b.mul(a, c, 50), ctx.number("8.5094"), 50), 50) == 0
    assert b.sign(b.sub(b.neg(a, 50), ctx.number("-3.14"), 50), 50) == 0
    assert b.sign(
        b.sub(b.abs_val(b.neg(a, 50), 50), a, 50), 50
    ) == 0


def test_pow(ctx):
    """Возведение в степень."""
    b = ctx.backend
    assert b.sign(
        b.sub(b.pow(ctx.number("2"), ctx.number("10"), 50),
              ctx.number("1024"), 50),
        50,
    ) == 0


def test_sign(ctx):
    """sign возвращает -1 / 0 / +1."""
    b = ctx.backend
    assert b.sign(ctx.number("-5"), 50) == -1
    assert b.sign(ctx.number("0"), 50) == 0
    assert b.sign(ctx.number("5"), 50) == 1


def test_digits_of_boundaries(ctx):
    """digits_of на границах."""
    b = ctx.backend
    # Идеальное совпадение — возвращает dps.
    assert b.digits_of(ctx.number("1.0"), ctx.number("1.0"), 50) == 50
    # |1.5 - 1.0| = 0.5 → floor(-log10(0.5)) = 0.
    assert b.digits_of(ctx.number("1.5"), ctx.number("1.0"), 50) == 0
    # |10 - 1| = 9 → floor(-log10(9)) = -1.
    assert b.digits_of(ctx.number("10"), ctx.number("1"), 50) < 0


def test_context_validation():
    """Context отвергает dps <= 0."""
    b = get_backend("mpmath")
    with pytest.raises(ValueError):
        Context(backend=b, dps=0)


# --- Матрица backend'ов -----------------------------------------------------

@pytest.mark.parametrize("dps", [20, 50])
def test_backends_agree_on_basics(dps):
    """
    Все доступные backend'ы согласны на базовых функциях.

    Сравниваем попарно через digits_of. Ожидаем ≥ dps - 5.
    """
    backends = list_backends()
    if len(backends) < 2:
        pytest.skip("нужно ≥2 backend'а для сравнения")

    fns = [
        ("sin",  lambda b, x: b.sin(b.number(x, dps), dps), "0.6"),
        ("cos",  lambda b, x: b.cos(b.number(x, dps), dps), "0.6"),
        ("exp",  lambda b, x: b.exp(b.number(x, dps), dps), "0.6"),
        ("log",  lambda b, x: b.log(b.number(x, dps), dps), "2"),
        ("zeta", lambda b, x: b.zeta(b.number(x, dps), dps), "3"),
    ]

    ref_name = backends[0]
    ref = get_backend(ref_name)
    for other_name in backends[1:]:
        other = get_backend(other_name)
        for name, fn, arg in fns:
            v1 = fn(ref, arg)
            v2 = fn(other, arg)
            d = ref.digits_of(v1, v2, dps)
            assert d >= dps - 5, (
                f"backends {ref_name} vs {other_name} на {name}: "
                f"только {d} знаков при dps={dps}"
            )