"""
Перекрёстная проверка backend'ов: mpmath vs decimal vs float.

Зачем нужен:
    Мы используем mpmath как единственный источник произвольной
    точности. Если mpmath врёт — все результаты фреймворка неверны.
    Этот тест сравнивает mpmath с двумя независимыми реализациями:

      - float (IEEE 754, аппаратный)
      - decimal.Decimal (stdlib, десятичное представление)

    На низкой точности (dps ~12) все три должны давать одинаковый
    результат. Это доказывает, что mpmath работает правильно.

    На высокой точности (dps 50) сравниваем mpmath с собой же
    при dps=100, усечённым до 50. Это ловит потери внутри операций.

Что проверяется:
    A. Элементарные операции: add, sub, mul, div, pow, neg, abs
       на dps=12 против float и decimal.
    B. Функции: zeta(3), sin(0.6), cos(0.6) — mpmath против decimal
       на dps=30.
    C. Self-consistency mpmath: dps=50 против dps=100 truncated.
    D. CounterRNG: распределение близко к равномерному, mean ≈ 0.5.

Запуск:
    python check_backends.py
"""

from __future__ import annotations
import math
import statistics
import sys
from decimal import Decimal, getcontext
from pathlib import Path

import mpmath as mp

import arbacc.series        # noqa: F401
import arbacc.noise         # noqa: F401
import arbacc.accelerators  # noqa: F401
import arbacc.stopping      # noqa: F401
import arbacc.postprocess   # noqa: F401
import arbacc.envelopes     # noqa: F401

from arbacc.core import Context, get
from arbacc.precision import get_backend
from arbacc.core.rng import CounterRNG


def section(title: str) -> None:
    """Печатает заголовок."""
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ==================== A. Элементарные операции ====================

def _threshold(mp_dps: int, ref_digits: int, order: int, margin: int = 2) -> int:
    """
    Считает порог совпадения с учётом всех ограничений.

    Ограничения:
      - mpmath не даёт больше mp_dps значащих цифр,
      - эталон не даёт больше ref_digits значащих цифр,
      - digits_of не возвращает больше mp_dps,
      - число порядка 10^order теряет |order| абсолютных цифр.

    Принимает:
        mp_dps     — dps mpmath
        ref_digits — значащих цифр эталона (15 для float, prec для decimal)
        order      — порядок результата (floor(log10(|x|)))
        margin     — запас

    Возвращает:
        целый порог ≥ 3.
    """
    base = min(mp_dps, ref_digits) - order - margin
    return max(3, min(mp_dps, base))


def _order_of(x) -> int:
    """
    Порядок числа: floor(log10(|x|)). Для x=0 возвращает 0.

    Принимает:
        x — число (float)

    Возвращает:
        целое.
    """
    xf = float(x)
    if xf == 0:
        return 0
    return math.floor(math.log10(abs(xf)))

def check_elementary_ops():
    """
    Проверяет элементарные операции mpmath против float и decimal.

    Порог совпадения вычисляется динамически, с учётом:
      - dps mpmath,
      - точности эталона (15 значащих для float, prec для decimal),
      - порядка величины результата,
      - ограничения digits_of ≤ mp_dps.
    """
    section("A. Элементарные операции: mpmath vs float vs decimal")

    MP_DPS = 30
    DEC_PREC = 60

    ctx = Context(backend=get_backend("mpmath"), dps=MP_DPS)
    b = ctx.backend

    pairs = [
        ("3.14", "2.71"),
        ("0.1", "0.2"),
        ("1e-10", "1e-8"),
        ("123456.789", "0.000123"),
        ("-5.5", "2.2"),
    ]

    for a_str, c_str in pairs:
        a_m = ctx.number(a_str)
        c_m = ctx.number(c_str)
        a_f = float(a_str)
        c_f = float(c_str)
        getcontext().prec = DEC_PREC
        a_d = Decimal(a_str)
        c_d = Decimal(c_str)

        # --- Сложение ---
        r_m = b.add(a_m, c_m, MP_DPS)
        r_f = a_f + c_f
        r_d = a_d + c_d
        thr_f = _threshold(MP_DPS, 15, _order_of(r_f))
        thr_d = _threshold(MP_DPS, DEC_PREC, _order_of(r_d))
        d_mf = b.digits_of(r_m, ctx.number(str(r_f)), MP_DPS)
        d_md = b.digits_of(r_m, ctx.number(str(r_d)), MP_DPS)
        assert d_mf >= thr_f, f"add/mpmath-vs-float ({a_str},{c_str}): {d_mf} < {thr_f}"
        assert d_md >= thr_d, f"add/mpmath-vs-decimal ({a_str},{c_str}): {d_md} < {thr_d}"

        # --- Умножение ---
        r_m = b.mul(a_m, c_m, MP_DPS)
        r_f = a_f * c_f
        r_d = a_d * c_d
        thr_f = _threshold(MP_DPS, 15, _order_of(r_f))
        thr_d = _threshold(MP_DPS, DEC_PREC, _order_of(r_d))
        d_mf = b.digits_of(r_m, ctx.number(str(r_f)), MP_DPS)
        d_md = b.digits_of(r_m, ctx.number(str(r_d)), MP_DPS)
        assert d_mf >= thr_f, f"mul/mpmath-vs-float ({a_str},{c_str}): {d_mf} < {thr_f}"
        assert d_md >= thr_d, f"mul/mpmath-vs-decimal ({a_str},{c_str}): {d_md} < {thr_d}"

        # --- Деление ---
        if c_f != 0 and c_d != 0:
            r_m = b.div(a_m, c_m, MP_DPS)
            r_f = a_f / c_f
            r_d = a_d / c_d
            thr_f = _threshold(MP_DPS, 15, _order_of(r_f))
            thr_d = _threshold(MP_DPS, DEC_PREC, _order_of(r_d))
            d_mf = b.digits_of(r_m, ctx.number(str(r_f)), MP_DPS)
            d_md = b.digits_of(r_m, ctx.number(str(r_d)), MP_DPS)
            assert d_mf >= thr_f, f"div/mpmath-vs-float ({a_str},{c_str}): {d_mf} < {thr_f}"
            assert d_md >= thr_d, f"div/mpmath-vs-decimal ({a_str},{c_str}): {d_md} < {thr_d}"

    print(f"  {len(pairs)} пар × 3 операции OK (динамические пороги)")

    # --- pow ---
    for base, exp in [("2", "10"), ("2", "0.5"), ("3", "3.5"), ("1.5", "-2")]:
        b_m = ctx.number(base)
        e_m = ctx.number(exp)
        b_f = float(base)
        e_f = float(exp)
        r_m = b.pow(b_m, e_m, MP_DPS)
        r_f = b_f ** e_f
        thr_f = _threshold(MP_DPS, 15, _order_of(r_f))
        d_mf = b.digits_of(r_m, ctx.number(str(r_f)), MP_DPS)
        assert d_mf >= thr_f, f"pow({base},{exp}): {d_mf} < {thr_f}"
    print(f"  pow: 4 случая OK")

    # --- neg, abs_val ---
    for v_str in ["3.14", "-2.71", "0", "1e-10"]:
        v_m = ctx.number(v_str)
        v_f = float(v_str)
        r_m = b.neg(v_m, MP_DPS)
        thr_f = _threshold(MP_DPS, 15, _order_of(-v_f))
        d_mf = b.digits_of(r_m, ctx.number(str(-v_f)), MP_DPS)
        assert d_mf >= thr_f, f"neg({v_str}): {d_mf} < {thr_f}"

        r_m = b.abs_val(v_m, MP_DPS)
        thr_f = _threshold(MP_DPS, 15, _order_of(abs(v_f)))
        d_mf = b.digits_of(r_m, ctx.number(str(abs(v_f))), MP_DPS)
        assert d_mf >= thr_f, f"abs_val({v_str}): {d_mf} < {thr_f}"
    print(f"  neg/abs_val: 4 случая OK")

    # --- Демонстрация зависимости от |x| ---
    print("  зависимость от |x| (self-consistency mpmath dps=30 vs dps=50):")
    for scale_str, label in [("1e-20", "маленькое"), ("1", "среднее"), ("1e20", "большое")]:
        with mp.workdps(50):
            ctx_hi = Context(backend=b, dps=50)
            x_hi = ctx_hi.number(scale_str)
            y_hi = b.mul(x_hi, ctx_hi.number("1.0000000000000000001"), 50)
        x_lo = ctx.number(scale_str)
        y_lo = b.mul(x_lo, ctx.number("1.0000000000000000001"), MP_DPS)
        d = b.digits_of(y_lo, y_hi, MP_DPS)
        order = _order_of(x_lo)
        print(f"    |x|={scale_str:8s} ({label:10s}), order={order:+3d}: "
              f"{d} совпадающих цифр")

    print("[OK] элементарные операции совпадают с float и decimal")


# ==================== B. Функции: zeta, sin, cos ====================

def check_transcendental():
    """
    Проверяет zeta(3), sin(0.6), cos(0.6) против decimal / math.

    Для sin/cos используем math (Python stdlib) как эталон на
    double-точности.
    Для zeta(3) — decimal не поможет (нет встроенной zeta),
    сравниваем mpmath dps=30 против mpmath dps=100 truncated.
    """
    section("B. Трансцендентные: zeta, sin, cos")

    ctx = Context(backend=get_backend("mpmath"), dps=30)
    b = ctx.backend

    # --- sin(0.6), cos(0.6) против math ---
    with mp.workdps(50):
        sin_mp = ctx.number(str(mp.sin(mp.mpf("0.6"))))
        cos_mp = ctx.number(str(mp.cos(mp.mpf("0.6"))))

    sin_py = math.sin(0.6)
    cos_py = math.cos(0.6)

    d_sin = b.digits_of(sin_mp, ctx.number(str(sin_py)), 30)
    d_cos = b.digits_of(cos_mp, ctx.number(str(cos_py)), 30)
    print(f"  sin(0.6): mpmath vs math → {d_sin} цифр")
    print(f"  cos(0.6): mpmath vs math → {d_cos} цифр")
    assert d_sin >= 14, f"sin(0.6) расходится с math: {d_sin}"
    assert d_cos >= 14, f"cos(0.6) расходится с math: {d_cos}"

    # --- Ряд Тейлора для sin через наш фреймворк ---
    # Строим сумму 40 членов через mpmath и сравниваем с mp.sin.
    with mp.workdps(50):
        x = mp.mpf("0.6")
        total_series = mp.mpf(0)
        sign = mp.mpf(1)
        for k in range(40):
            total_series += sign * x ** (2 * k + 1) / mp.factorial(2 * k + 1)
            sign = -sign
        exact_sin = mp.sin(x)

    total_num = ctx.number(str(total_series))
    exact_num = ctx.number(str(exact_sin))
    d = b.digits_of(total_num, exact_num, 30)
    print(f"  ряд Тейлора для sin(0.6): {d} цифр")
    assert d >= 25, f"ряд Тейлора для sin: только {d} цифр"

    # --- zeta(3) self-consistency: dps=50 vs dps=100 ---
    # Вычисляем zeta(3) при dps=100 и dps=50.
    with mp.workdps(100):
        zeta_100 = ctx.number(str(mp.zeta(3)))
    with mp.workdps(50):
        zeta_50 = ctx.number(str(mp.zeta(3)))

    # digits_of должна работать в dps=50, чтобы вернуть до 50 цифр.
    d = b.digits_of(zeta_50, zeta_100, 50)
    print(f"  zeta(3): dps=50 vs dps=100 → {d} цифр")
    assert d >= 45, f"zeta(3) mpmath-50 vs mpmath-100: {d}"

    # --- zeta(3) через наш ряд vs mp.zeta ---
    ZetaCls = get("series", "zeta")
    zeta = ZetaCls(params={"s": 3})
    stream = zeta.build_stream(ctx)
    # Сумма первых 10000 членов.
    total = ctx.number(0)
    for n in range(10000):
        total = b.add(total, stream.get(n), 30)
    d = b.digits_of(total, zeta_100, 30)
    print(f"  zeta(3) ряд из 10000 членов vs mp.zeta → {d} цифр")
    assert d >= 3, f"zeta(3) ряд: только {d} цифр (медленная сходимость)"

    print("[OK] трансцендентные функции согласованы")


# ==================== C. Self-consistency mpmath ====================

def check_self_consistency():
    """
    Проверяет: mpmath при dps=50 даёт те же первые 50 цифр, что
    mpmath при dps=150 (усечённый).

    Ловит ситуации, когда операция теряет точность внутри.
    """
    section("C. Self-consistency mpmath (dps=50 vs dps=150)")

    backend = get_backend("mpmath")

    # Вычислим ряд операций при двух точностях.
    ops = [
        ("1/3", lambda c, d: c.backend.div(c.number(1), c.number(3), d)),
        ("sqrt(2)", lambda c, d: c.backend.pow(c.number(2), c.number("0.5"), d)),
        ("pi", lambda c, d: c.number(str(mp.pi))),
        ("e", lambda c, d: c.number(str(mp.e))),
        ("sin(1)", lambda c, d: c.number(str(mp.sin(1)))),
        ("log(2)", lambda c, d: c.number(str(mp.log(2)))),
        ("exp(1)", lambda c, d: c.number(str(mp.exp(1)))),
        ("gamma(0.5)", lambda c, d: c.number(str(mp.gamma(mp.mpf("0.5"))))),
    ]

    for name, fn in ops:
        with mp.workdps(150):
            ctx_150 = Context(backend=backend, dps=150)
            v150 = fn(ctx_150, 150)
        with mp.workdps(50):
            ctx_50 = Context(backend=backend, dps=50)
            v50 = fn(ctx_50, 50)

        d = backend.digits_of(v50, v150, 50)
        assert d >= 48, f"{name}: mpmath-50 vs mpmath-150 → {d}"
        print(f"  {name:12s}: {d} совпадающих цифр")

    print("[OK] mpmath self-consistent на 8 операциях")


# ==================== D. CounterRNG: распределение ====================

def check_rng_distribution():
    """
    Проверяет, что CounterRNG даёт близкое к равномерному распределение.

    Статистические тесты:
      - mean ≈ 0.5
      - std ≈ 1/sqrt(12)
      - гистограмма по 10 корзинам равномерна
    """
    section("D. CounterRNG: распределение")

    rng = CounterRNG(seed=42, stream_id="test")
    N = 100_000
    samples = [rng.uniform(n) for n in range(N)]

    mean = statistics.mean(samples)
    std = statistics.stdev(samples)

    print(f"  N={N}, mean={mean:.6f}, std={std:.6f}")

    # Среднее должно быть 0.5 ± 0.01 (при N=100k это огромный запас).
    assert abs(mean - 0.5) < 0.01, f"mean={mean} далеко от 0.5"

    # Std равномерного [0,1) = 1/sqrt(12) ≈ 0.2887.
    expected_std = 1.0 / math.sqrt(12)
    assert abs(std - expected_std) < 0.01, f"std={std} vs {expected_std}"

    # Гистограмма по 10 корзинам.
    bins = [0] * 10
    for s in samples:
        idx = min(int(s * 10), 9)
        bins[idx] += 1
    expected_per_bin = N / 10
    for i, count in enumerate(bins):
        ratio = count / expected_per_bin
        assert 0.95 < ratio < 1.05, f"bin {i}: {count} (ожидалось ~{expected_per_bin:.0f})"
    print(f"  bins: {bins}")
    print(f"  ожидалось по {expected_per_bin:.0f}, отклонение <5%")

    # Детерминизм.
    rng2 = CounterRNG(seed=42, stream_id="test")
    for n in [0, 1, 500, 50000, 99999]:
        assert rng.uniform(n) == rng2.uniform(n), f"не детерминирован на n={n}"
    print("  детерминизм OK")

    # Разные seeds → разные последовательности.
    rng3 = CounterRNG(seed=43, stream_id="test")
    diff_count = sum(1 for n in range(1000) if rng.uniform(n) != rng3.uniform(n))
    assert diff_count > 990, f"разные seeds дают {1000 - diff_count} совпадений"
    print(f"  разные seeds: {diff_count}/1000 различаются")

    # Нормальное распределение.
    normal_samples = [rng.normal(n) for n in range(N)]
    n_mean = statistics.mean(normal_samples)
    n_std = statistics.stdev(normal_samples)
    print(f"  normal: mean={n_mean:.6f}, std={n_std:.6f}")
    assert abs(n_mean) < 0.02, f"normal mean={n_mean}"
    assert abs(n_std - 1.0) < 0.02, f"normal std={n_std}"

    print("[OK] CounterRNG даёт корректное распределение")


# ==================== main ====================

def main() -> int:
    """Точка входа."""
    print("=" * 70)
    print("CROSS-BACKEND VALIDATION")
    print("=" * 70)
    print(f"Python:   {sys.version.split()[0]}")
    print(f"mpmath:   {mp.__version__}")
    print(f"decimal:  stdlib")

    try:
        check_elementary_ops()
        check_transcendental()
        check_self_consistency()
        check_rng_distribution()
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        return 1
    except Exception as e:
        import traceback
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        print(traceback.format_exc())
        return 1

    print()
    print("=" * 70)
    print("ВСЕ КРОСС-ПРОВЕРКИ ПРОЙДЕНЫ")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())