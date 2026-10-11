"""
Генератор тестовых файлов для проверки from_file.

Создаёт в examples/data/:
    sin_06.csv, sin_06.txt, cos_06.csv, cos_06.txt

Записываются ЧЛЕНЫ ряда a_n (не частичные суммы).

Формат:
    CSV — заголовок "value", затем по одному члену в строке.
    TXT — по одному члену в строке, без заголовка.

    Числа пишутся через str(mpf) — mpmath гарантирует полную точность.

Запуск:
    python generate_series_files.py
"""

from __future__ import annotations
from pathlib import Path

import mpmath as mp


#: Точка разложения.
X = "0.6"

#: Сколько членов записать.
N_TERMS = 60

#: Точность при генерации (заведомо больше, чем dps пользователя).
DPS = 150


def sin_terms(x: str, n: int) -> list[str]:
    """
    Члены ряда Тейлора для sin(x):
        a_k = (-1)^k * x^(2k+1) / (2k+1)!
    """
    out: list[str] = []
    with mp.workdps(DPS):
        xm = mp.mpf(x)
        sign = mp.mpf(1)
        for k in range(n):
            fact = mp.factorial(2 * k + 1)
            a = sign * xm ** (2 * k + 1) / fact
            # str(mpf) даёт полное представление без потерь.
            out.append(str(a))
            sign = -sign
    return out


def cos_terms(x: str, n: int) -> list[str]:
    """
    Члены ряда Тейлора для cos(x):
        a_k = (-1)^k * x^(2k) / (2k)!
    """
    out: list[str] = []
    with mp.workdps(DPS):
        xm = mp.mpf(x)
        sign = mp.mpf(1)
        for k in range(n):
            fact = mp.factorial(2 * k)
            a = sign * xm ** (2 * k) / fact
            out.append(str(a))
            sign = -sign
    return out


def write_csv(path: Path, values: list[str]) -> None:
    """CSV с заголовком value."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("value\n")
        for v in values:
            f.write(v + "\n")


def write_txt(path: Path, values: list[str]) -> None:
    """TXT — по одному числу в строке."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for v in values:
            f.write(v + "\n")


def main() -> None:
    """Генерирует 4 файла."""
    data_dir = Path(__file__).parent / "examples" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    s = sin_terms(X, N_TERMS)
    c = cos_terms(X, N_TERMS)

    write_csv(data_dir / "sin_06.csv", s)
    write_txt(data_dir / "sin_06.txt", s)
    write_csv(data_dir / "cos_06.csv", c)
    write_txt(data_dir / "cos_06.txt", c)

    print(f"Written to {data_dir}:")
    for name in ("sin_06.csv", "sin_06.txt", "cos_06.csv", "cos_06.txt"):
        p = data_dir / name
        print(f"  {p.name:20s}  {p.stat().st_size:6d} bytes")

    with mp.workdps(DPS):
        print(f"\nsin(0.6) = {mp.nstr(mp.sin(mp.mpf(X)), 80)}")
        print(f"cos(0.6) = {mp.nstr(mp.cos(mp.mpf(X)), 80)}")


if __name__ == "__main__":
    main()