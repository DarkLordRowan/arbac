"""
Проверка backend'ов против НЕЗАВИСИМЫХ источников.

Три уровня независимости:

    1. Опубликованные математические константы (Wikipedia/Wolfram).
       sin(0.6), cos(0.6), zeta(3), gamma(0.5), ... — эти числа
       известны с точностью >60 знаков и многократно проверены.

    2. Python decimal (stdlib).
       Полностью независимая реализация арифметики. Не имеет
       sin/cos/zeta, но имеет +, -, *, /, sqrt, exp, ln.

    3. math (IEEE 754 double).
       15-16 значащих, независимо от mpmath и arb.

Если все три источника согласны с backend'ом до уровня dps —
backend работает корректно.

Запуск:
    python check_backends_reference.py
"""

from __future__ import annotations
import math
import sys
from decimal import Decimal, getcontext

import arbacc.precision  # noqa: F401 — autodiscovery
from arbacc.precision import list_backends, get_backend


#: Опубликованные константы для трансцендентных тестов.
#: Точность — до 60-70 знаков (см. Wikipedia / Wolfram Alpha).
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



#: Как вычислить каждое значение через backend.
def _compute(b, name: str, dps: int):
    """Вычисляет значение теста через backend b."""
    if name == "sin(0.6)":
        return b.sin(b.number("0.6", dps), dps)
    if name == "cos(0.6)":
        return b.cos(b.number("0.6", dps), dps)
    if name == "exp(0.6)":
        return b.exp(b.number("0.6", dps), dps)
    if name == "log(2)":
        return b.log(b.number("2", dps), dps)
    if name == "sqrt(2)":
        return b.pow(b.number("2", dps), b.number("0.5", dps), dps)
    if name == "zeta(3)":
        return b.zeta(b.number("3", dps), dps)
    if name == "zeta(5)":
        return b.zeta(b.number("5", dps), dps)
    if name == "gamma(0.5)":
        return b.gamma(b.number("0.5", dps), dps)
    raise ValueError(name)


def section_a_constants(backends: list[str]):
    """Раздел A: сравнение с опубликованными константами."""
    print("=" * 76)
    print("A. Сравнение с опубликованными константами")
    print("=" * 76)
    print("   (эти числа известны с точностью 60+ знаков из независимых источников)")
    print()

    instances = {n: get_backend(n) for n in backends}

    for dps in (20, 40, 60):
        header = f"{'test':14s} " + " ".join(f"{b:>10s}" for b in backends)
        print(f"--- dps = {dps} ---")
        print(header)
        print("-" * len(header))
        for name in REFS:
            cells = []
            for b_name in backends:
                b = instances[b_name]
                try:
                    v = _compute(b, name, dps)
                    ref = b.number(REFS[name], dps)
                    d = b.digits_of(v, ref, dps)
                except Exception as e:
                    d = -1
                    print(f"    [ERROR] {b_name} {name}: {type(e).__name__}: {e}")
                cells.append(f"{d:>10d}")
            print(f"{name:14s} " + " ".join(cells))
        print()


def section_b_decimal(backends: list[str]):
    """Раздел B: сравнение с Python Decimal на арифметике."""
    print("=" * 76)
    print("B. Сравнение с Python Decimal (независимая реализация арифметики)")
    print("=" * 76)
    print("   (Decimal из stdlib, не имеет sin/cos/zeta, но имеет +, -, *, /, sqrt)")
    print()

    instances = {n: get_backend(n) for n in backends}

    # Тесты: (имя, лямбда(Decimal a, Decimal b), лямбда(backend a, backend b, dps))
    OPS = [
        ("3.14 + 2.71", lambda a, b: a + b,
         lambda bk, a, b, dps: bk.add(a, b, dps)),
        ("3.14 - 2.71", lambda a, b: a - b,
         lambda bk, a, b, dps: bk.sub(a, b, dps)),
        ("3.14 * 2.71", lambda a, b: a * b,
         lambda bk, a, b, dps: bk.mul(a, b, dps)),
        ("3.14 / 2.71", lambda a, b: a / b,
         lambda bk, a, b, dps: bk.div(a, b, dps)),
        ("123456.789 + 0.000123", lambda a, b: a + b,
         lambda bk, a, b, dps: bk.add(a, b, dps)),
        ("1e-10 * 1e-8", lambda a, b: a * b,
         lambda bk, a, b, dps: bk.mul(a, b, dps)),
    ]

    for dps in (20, 50, 100):
        getcontext().prec = dps + 20
        header = f"{'op':24s} " + " ".join(f"{b:>10s}" for b in backends)
        print(f"--- dps = {dps} ---")
        print(header)
        print("-" * len(header))
        for name, dec_op, bk_op in OPS:
            a_str, b_str = name.split()[0], name.split()[2]
            a_dec = Decimal(a_str)
            b_dec = Decimal(b_str)
            ref_dec = dec_op(a_dec, b_dec)
            cells = []
            for b_name in backends:
                bk = instances[b_name]
                try:
                    a_num = bk.number(a_str, dps)
                    b_num = bk.number(b_str, dps)
                    got = bk_op(bk, a_num, b_num, dps)
                    ref = bk.number(str(ref_dec), dps)
                    d = bk.digits_of(got, ref, dps)
                except Exception as e:
                    d = -1
                    print(f"    [ERROR] {b_name} {name}: {type(e).__name__}: {e}")
                cells.append(f"{d:>10d}")
            print(f"{name:24s} " + " ".join(cells))
        print()


def section_c_float(backends: list[str]):
    """Раздел C: сравнение с math (double)."""
    print("=" * 76)
    print("C. Сравнение с math (IEEE 754 double, ~15 цифр)")
    print("=" * 76)
    print()

    instances = {n: get_backend(n) for n in backends}

    FLOAT_TESTS = [
        ("sin(0.6)", math.sin(0.6)),
        ("cos(0.6)", math.cos(0.6)),
        ("exp(0.6)", math.exp(0.6)),
        ("log(2)",   math.log(2)),
        ("sqrt(2)",  math.sqrt(2)),
    ]

    header = f"{'test':14s} " + " ".join(f"{b:>10s}" for b in backends)
    print(header)
    print("-" * len(header))
    for name, ref_float in FLOAT_TESTS:
        cells = []
        for b_name in backends:
            b = instances[b_name]
            try:
                v = _compute(b, name, 30)
                ref = b.number(repr(ref_float), 30)
                d = b.digits_of(v, ref, 30)
            except Exception:
                d = -1
            cells.append(f"{d:>10d}")
        print(f"{name:14s} " + " ".join(cells))
    print()
    print("   (ожидаем ~14-15 знаков — это предел double)")
    print()


def main() -> int:
    backends = list_backends()
    print("=" * 76)
    print("REFERENCE VALIDATION")
    print("=" * 76)
    print(f"available backends: {backends}")
    print()

    if not backends:
        print("Нет доступных backend'ов.")
        return 1

    section_a_constants(backends)
    section_b_decimal(backends)
    section_c_float(backends)

    print("=" * 76)
    print("Ожидаемые значения:")
    print("  A (константы)   : dps, до 60 (предел констант)")
    print("  B (Decimal)     : dps - 2 ... dps (запас на округление)")
    print("  C (float/math)  : 14-15 (предел double)")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())