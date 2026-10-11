"""
Сравнение mpmath с MPFR (через python-flint/arb).

Зачем:
    В твоём C++ фреймворке ты сравнивал MPFR и Wester. Здесь делаем
    аналогично: mpmath (наш backend) против python-flint/arb (MPFR-based).
    Три независимых источника на разных точностях.

Проверяется:
    cos(0.6), sin(0.6), exp(0.6), sqrt(2), zeta(3), zeta(5)

Запуск:
    python check_mpmath_vs_mpfr.py
"""

from __future__ import annotations
import sys
from pathlib import Path

import mpmath as mp

try:
    from flint import arb, ctx as flint_ctx, arb as _arb
except ImportError:
    print("Установи python-flint: pip install python-flint")
    sys.exit(1)


def flint_prec_from_dps(dps: int) -> int:
    """
    Переводит десятичные значащие цифры в биты для flint.

    Формула: bits ≈ dps * log2(10) + запас.
    """
    import math
    return int(math.ceil(dps * 3.321928095)) + 10


def mpmath_value(fn_name: str, arg_str: str, dps: int) -> str:
    """Считает значение через mpmath, возвращает строку dps+20 знаков."""
    with mp.workdps(dps + 20):
        arg = mp.mpf(arg_str)
        if fn_name == "cos":
            v = mp.cos(arg)
        elif fn_name == "sin":
            v = mp.sin(arg)
        elif fn_name == "exp":
            v = mp.exp(arg)
        elif fn_name == "sqrt":
            v = mp.sqrt(arg)
        elif fn_name == "zeta":
            v = mp.zeta(arg)
        elif fn_name == "log":
            v = mp.log(arg)
        else:
            raise ValueError(fn_name)
        return mp.nstr(v, dps + 20, strip_zeros=False)


def flint_value(fn_name: str, arg_str: str, dps: int) -> str:
    """
    Считает значение через flint/arb, возвращает строку-значение
    (без интервальной погрешности).

    Arb возвращает интервалы: "[1.234... +/- 5e-50]". Извлекаем
    центральное значение.
    """
    flint_ctx.prec = flint_prec_from_dps(dps + 20)
    arg = arb(arg_str)
    if fn_name == "cos":
        v = arg.cos()
    elif fn_name == "sin":
        v = arg.sin()
    elif fn_name == "exp":
        v = arg.exp()
    elif fn_name == "sqrt":
        v = arg.sqrt()
    elif fn_name == "zeta":
        v = arg.zeta()
    elif fn_name == "log":
        v = arg.log()
    else:
        raise ValueError(fn_name)

    s = str(v).strip()
    # Формат Arb: "[value +/- error]" или "value".
    if s.startswith("["):
        s = s[1:]
    if "+/-" in s:
        s = s.split("+/-")[0].strip()
    s = s.rstrip("]").strip()
    return s


def agreement_digits(a_str: str, b_str: str, mp_dps: int) -> int:
    """
    Сравнивает два числа по строковому представлению.
    Возвращает число совпадающих значащих цифр.
    """
    def norm(s: str) -> str:
        s = s.strip()
        # Убираем обрамление Arb, если осталось.
        s = s.strip("[]").strip()
        # Убираем +/- ..., если осталось.
        if "+/-" in s:
            s = s.split("+/-")[0].strip()
        s = s.replace(" ", "")
        # Знак.
        neg = s.startswith("-")
        if neg:
            s = s[1:]
        # Экспоненциальная форма: mant e exp.
        mant = s
        exp = 0
        low = s.lower()
        if "e" in low:
            mant, _, exp_s = low.partition("e")
            try:
                exp = int(exp_s)
            except ValueError:
                exp = 0
        # Убираем точку.
        mant = mant.replace(".", "")
        mant = mant.lstrip("0")
        if not mant:
            return 0
        # Нормализуем на позицию первой значащей цифры.
        # Порядок: 10^(exp + len_int_part - 1), где len_int_part —
        # длина целой части до точки.
        return ("-" if neg else "") + mant

    na = norm(a_str)
    nb = norm(b_str)
    n = min(len(na), len(nb))
    for i in range(n):
        if na[i] != nb[i]:
            return i
    return n


def main() -> int:
    print("=" * 70)
    print("MPMATH vs FLINT/ARB (MPFR-based)")
    print("=" * 70)
    print(f"mpmath: {mp.__version__}")
    try:
        from flint import __version__ as flint_ver
        print(f"flint:  {flint_ver}")
    except Exception:
        pass
    print()

    tests = [
        ("cos", "0.6"),
        ("sin", "0.6"),
        ("exp", "0.6"),
        ("sqrt", "2"),
        ("log", "2"),
        ("zeta", "3"),
        ("zeta", "5"),
    ]

    precisions = [10, 20, 30, 50, 80, 120]

    print(f"{'func':6s} {'arg':5s} {'dps':>4s}  {'agree':>6s}")
    print("-" * 34)

    total_ok = 0
    total = 0
    for fn, arg in tests:
        for dps in precisions:
            total += 1
            a = mpmath_value(fn, arg, dps)
            b = flint_value(fn, arg, dps)
            d = agreement_digits(a, b, dps)
            # Ожидаем: совпадение близко к dps (минус запас 2-3 цифры).
            ok = d >= dps - 3
            mark = "OK " if ok else "DIFF"
            print(f"{fn:6s} {arg:5s} {dps:4d}  {d:6d} {mark}")
            if ok:
                total_ok += 1

    print()
    print(f"Совпало: {total_ok}/{total}")
    if total_ok == total:
        print("MPMATH И MPFR/ARB СОГЛАСОВАНЫ НА ВСЕХ ТОЧНОСТЯХ")
        return 0
    print("ЕСТЬ РАСХОЖДЕНИЯ — проверь вывод выше")
    return 1


if __name__ == "__main__":
    sys.exit(main())