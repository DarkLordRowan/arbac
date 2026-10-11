"""
Генерация эталонных констант для check_backends_reference.py.

Зачем:
    arb (интервальная арифметика) сам сообщает погрешность: результат
    возвращается как [значение ± err]. Если err < 10^-70, значит
    значение верно до 70 знаков — это ГАРАНТИЯ, а не «два источника
    согласны».

    Этот скрипт генерирует константы через arb при 300-битной точности
    (~90 десятичных цифр) и печатает их в формате Python-строк,
    готовом для вставки в REFS.

Запуск:
    python generate_constants.py
"""

from __future__ import annotations
from flint import arb, ctx as flint_ctx


#: 300 бит ≈ 90 десятичных цифр.
flint_ctx.prec = 300


def show(name: str, v: arb) -> None:
    """
    Печатает строку в формате REFS['name'] = '...'.

    Извлекает центр и погрешность; показывает погрешность отдельно.
    """
    s = str(v)
    # s = "[center +/- err]"
    if s.startswith("["):
        s = s[1:]
    if "+/-" in s:
        center, err = s.split("+/-")
        center = center.strip()
        err = err.rstrip("]").strip()
    else:
        center = s.rstrip("]").strip()
        err = "?"

    # Форматируем как Python-строку, готовую для вставки.
    print(f'    "{name}":')
    print(f'        "{center}",')
    print(f'    # err = {err}')
    print()


def main() -> None:
    print('REFS = {')
    show("sin(0.6)",   arb("0.6").sin())
    show("cos(0.6)",   arb("0.6").cos())
    show("exp(0.6)",   arb("0.6").exp())
    show("log(2)",     arb(2).log())
    show("sqrt(2)",    arb(2).sqrt())
    show("zeta(3)",    arb(3).zeta())
    show("zeta(5)",    arb(5).zeta())
    show("gamma(0.5)", arb("0.5").gamma())
    print('}')


if __name__ == "__main__":
    main()