"""
Сравнение backend'ов с НЕЗАВИСИМЫМИ источниками.

Три уровня:
    A. Опубликованные константы (sin, cos, exp, log, zeta, gamma).
    B. Python Decimal (арифметика).
    C. math (IEEE 754 double, ~15 цифр).
"""

from __future__ import annotations
from decimal import Decimal, getcontext

import pytest

from arbacc.precision import list_backends, get_backend


#: Опубликованные константы (60+ знаков).
REFS = {
    "sin(0.6)":
        "0.56464247339503535720094544565865790710988808499415177102426589426735593023496609217226420",
    # err = 1.42e-90

    "cos(0.6)":
        "0.82533561490967829724095249895537603887809103918847038136974977367156928181352306340400265",
    # err = 4.31e-90

    "exp(0.6)":
        "1.8221188003905089748753676681628645133822388085464353863205474765888196502986192375060718",
    # err = 4.32e-89

    "log(2)":
        "0.69314718055994530941723212145817656807550013436025525412068000949339362196969471560586333",
    # err = 3.92e-90

    "sqrt(2)":
        "1.4142135623730950488016887242096980785696718753769480731766797379907324784621070388503875",
    # err = 3.48e-89

    "zeta(3)":
        "1.2020569031595942853997381615114499907649862923404988817922715553418382057863130901864559",
    # err = 2.78e-89

    "zeta(5)":
        "1.0369277551433699263313654864570341680570809195019128119741926779038035897862814845600431",
    # err = 6.77e-90

    "gamma(0.5)":
        "1.7724538509055160272981674833411451827975494561223871282138077898529112845910321813749507",
    # err = 4.52e-89

}



def _compute(b, name: str, dps: int):
    """Вычисляет значение теста через backend b."""
    if name == "sin(0.6)":   return b.sin(b.number("0.6", dps), dps)
    if name == "cos(0.6)":   return b.cos(b.number("0.6", dps), dps)
    if name == "exp(0.6)":   return b.exp(b.number("0.6", dps), dps)
    if name == "log(2)":     return b.log(b.number("2", dps), dps)
    if name == "sqrt(2)":    return b.pow(b.number("2", dps),
                                          b.number("0.5", dps), dps)
    if name == "zeta(3)":    return b.zeta(b.number("3", dps), dps)
    if name == "zeta(5)":    return b.zeta(b.number("5", dps), dps)
    if name == "gamma(0.5)": return b.gamma(b.number("0.5", dps), dps)
    raise ValueError(name)


# --- Раздел A: против констант ----------------------------------------------

@pytest.mark.parametrize("backend_name", list_backends())
@pytest.mark.parametrize("name", list(REFS.keys()))
@pytest.mark.parametrize("dps", [20, 40, 60])
def test_vs_published_constants(backend_name, name, dps):
    """Backend согласен с опубликованной константой до dps знаков."""
    b = get_backend(backend_name)
    v = _compute(b, name, dps)
    ref = b.number(REFS[name], dps)
    d = b.digits_of(v, ref, dps)
    assert d >= dps - 3, (
        f"{backend_name} на {name} при dps={dps}: только {d} знаков"
    )


# --- Раздел B: против Decimal -----------------------------------------------

DECIMAL_OPS = [
    ("3.14 + 2.71", "3.14", "2.71",
     lambda a, b: a + b,
     lambda bk, a, b, dps: bk.add(a, b, dps)),
    ("3.14 - 2.71", "3.14", "2.71",
     lambda a, b: a - b,
     lambda bk, a, b, dps: bk.sub(a, b, dps)),
    ("3.14 * 2.71", "3.14", "2.71",
     lambda a, b: a * b,
     lambda bk, a, b, dps: bk.mul(a, b, dps)),
    ("3.14 / 2.71", "3.14", "2.71",
     lambda a, b: a / b,
     lambda bk, a, b, dps: bk.div(a, b, dps)),
    ("1e-10 * 1e-8", "1e-10", "1e-8",
     lambda a, b: a * b,
     lambda bk, a, b, dps: bk.mul(a, b, dps)),
]


@pytest.mark.parametrize("backend_name", list_backends())
@pytest.mark.parametrize("name,a_str,b_str,dec_op,bk_op", DECIMAL_OPS)
@pytest.mark.parametrize("dps", [20, 50])
def test_vs_decimal(backend_name, name, a_str, b_str,
                    dec_op, bk_op, dps):
    """Арифметика backend'а совпадает с Decimal."""
    getcontext().prec = dps + 20
    ref_dec = dec_op(Decimal(a_str), Decimal(b_str))

    b = get_backend(backend_name)
    a_num = b.number(a_str, dps)
    b_num = b.number(b_str, dps)
    got = bk_op(b, a_num, b_num, dps)
    ref = b.number(str(ref_dec), dps)
    d = b.digits_of(got, ref, dps)

    # Порог: dps - 5 (из-за округления в Decimal и в backend).
    assert d >= dps - 5, (
        f"{backend_name} на {name} при dps={dps}: только {d} знаков"
    )


# --- Раздел C: против math --------------------------------------------------

import math


FLOAT_TESTS = [
    ("sin(0.6)", math.sin(0.6)),
    ("cos(0.6)", math.cos(0.6)),
    ("exp(0.6)", math.exp(0.6)),
    ("log(2)",   math.log(2)),
    ("sqrt(2)",  math.sqrt(2)),
]


@pytest.mark.parametrize("backend_name", list_backends())
@pytest.mark.parametrize("name,ref_float", FLOAT_TESTS)
def test_vs_math(backend_name, name, ref_float):
    """
    Backend согласен с math до 13 знаков (у double 15-16).

    Порог 13 — с запасом на погрешность double.
    """
    b = get_backend(backend_name)
    v = _compute(b, name, 30)
    ref = b.number(repr(ref_float), 30)
    d = b.digits_of(v, ref, 30)
    assert d >= 13, (
        f"{backend_name} на {name} vs math: только {d} знаков"
    )