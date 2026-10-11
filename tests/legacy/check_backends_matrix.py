"""
Матрица попарного согласия между всеми доступными backend'ами.

Для каждой пары (b1, b2) показывает, сколько значащих цифр совпадает
на элементарных операциях и трансцендентных функциях.

Запуск:
    python check_backends_matrix.py
"""

from __future__ import annotations
import sys

import arbacc.precision  # noqa: F401  — autodiscovery
from arbacc.precision import list_backends, get_backend


#: Набор тестов: (имя, лямбда(backend, dps) -> число).
#: Все лямбды возвращают значение в представлении backend'а.
TESTS = [
    ("sin(0.6)",    lambda b, dps: b.sin(b.number("0.6", dps), dps)),
    ("cos(0.6)",    lambda b, dps: b.cos(b.number("0.6", dps), dps)),
    ("exp(0.6)",    lambda b, dps: b.exp(b.number("0.6", dps), dps)),
    ("log(2)",      lambda b, dps: b.log(b.number("2", dps), dps)),
    ("sqrt(2)",     lambda b, dps: b.pow(b.number("2", dps),
                                          b.number("0.5", dps), dps)),
    ("zeta(3)",     lambda b, dps: b.zeta(b.number("3", dps), dps)),
    ("zeta(5)",     lambda b, dps: b.zeta(b.number("5", dps), dps)),
    ("gamma(0.5)",  lambda b, dps: b.gamma(b.number("0.5", dps), dps)),
]

DPS_LIST = [20, 50, 100]


def agreement(b1, b2, fn, dps: int) -> int:
    """
    Возвращает число совпадающих значащих цифр между b1 и b2 на тесте fn.

    Принимает:
        b1, b2 — экземпляры backend'ов.
        fn     — лямбда (backend, dps) -> значение.
        dps    — точность.

    Возвращает:
        целое число цифр, или -1 при ошибке.
    """
    try:
        v1 = fn(b1, dps)
        v2 = fn(b2, dps)
    except Exception as e:
        print(f"    [ERROR] {type(e).__name__}: {e}")
        return -1
    try:
        return b1.digits_of(v1, v2, dps)
    except Exception:
        return -2


def main() -> int:
    backends = list_backends()
    print("=" * 70)
    print("BACKEND MATRIX")
    print("=" * 70)
    print(f"available: {backends}")
    print()

    if not backends:
        print("Нет доступных backend'ов — нечего сравнивать.")
        return 1

    instances = {n: get_backend(n) for n in backends}

    for dps in DPS_LIST:
        print(f"--- dps = {dps} ---")
        # Заголовок.
        header = f"{'test':14s} " + " ".join(f"{b:>10s}" for b in backends)
        print(header)
        print("-" * len(header))

        for name, fn in TESTS:
            cells = []
            # Сравниваем каждый backend с первым (эталоном).
            ref = backends[0]
            for b in backends:
                d = agreement(instances[ref], instances[b], fn, dps)
                cells.append(f"{d:>10d}")
            print(f"{name:14s} " + " ".join(cells))
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())