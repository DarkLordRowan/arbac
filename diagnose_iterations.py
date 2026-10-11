"""
Диагностика: сколько записей в iterations задачи.

Запуск:
    python diagnose_iterations.py out/exp_001/accel/zeta_s3/none/aitken_delta2_dps30
    python diagnose_iterations.py out/exp_001/accel       # все задачи
"""

from __future__ import annotations
import sys
from pathlib import Path


def _check_one(accel_dir: Path) -> None:
    """Печатает статистику по одной задаче."""
    base = accel_dir / "iterations"

    rows = None
    used_file = None
    for ext in (".parquet", ".jsonl.gz", ".jsonl"):
        p = base.with_suffix(ext)
        if p.exists():
            used_file = p
            break

    if used_file is None:
        print(f"  [нет файла] {accel_dir}")
        return

    from arbacc.storage import load_iterations
    rows = load_iterations(base)

    print(f"  file: {used_file.name}  size={used_file.stat().st_size}B  "
          f"rows={len(rows)}")

    if rows:
        first = rows[0]
        last = rows[-1]
        print(f"    first: k={first.get('k')} n_used={first.get('n_used')} "
              f"est={str(first.get('estimate'))[:40]}...")
        print(f"    last:  k={last.get('k')} n_used={last.get('n_used')} "
              f"est={str(last.get('estimate'))[:40]}...")

    # Из result.json — сколько итераций ожидается.
    rj = accel_dir / "result.json"
    if rj.exists():
        import json
        try:
            data = json.loads(rj.read_text(encoding="utf-8"))
            print(f"    result.json: n_used={data.get('n_used')} "
                  f"stopped_by={data.get('stopped_by')} "
                  f"digits_gained={data.get('digits_gained')}")
        except Exception as e:
            print(f"    result.json: ошибка {e}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return

    root = Path(sys.argv[1])
    if not root.exists():
        print(f"Путь не найден: {root}")
        return

    # Один accel-каталог.
    if (root / "result.json").exists():
        print(f"{root}:")
        _check_one(root)
        return

    # Всё дерево.
    accel_root = root
    if (root / "accel").exists():
        accel_root = root / "accel"

    n = 0
    for result_json in sorted(accel_root.rglob("result.json")):
        accel_dir = result_json.parent
        print(f"{accel_dir.relative_to(accel_root.parent)}:")
        _check_one(accel_dir)
        n += 1
        if n >= 30:
            print("... (показаны первые 30)")
            break

    if n == 0:
        print("Задач не найдено.")


if __name__ == "__main__":
    main()