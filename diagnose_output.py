"""
Диагностика хранилища output: что и сколько занимает.

Запуск:
    python diagnose_output.py out
"""

from __future__ import annotations
import sys
from pathlib import Path
from collections import defaultdict


def human(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def main(root_str: str) -> None:
    root = Path(root_str)
    if not root.exists():
        print(f"Путь не найден: {root}")
        return

    by_ext: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    files: list[tuple[int, Path]] = []

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            sz = p.stat().st_size
        except OSError:
            continue
        name = p.name
        if name.endswith(".jsonl.gz"):
            ext = ".jsonl.gz"
        elif name.endswith(".jsonl"):
            ext = ".jsonl"
        elif name.endswith(".parquet"):
            ext = ".parquet"
        else:
            ext = p.suffix or "<none>"
        by_ext[ext][0] += 1
        by_ext[ext][1] += sz
        files.append((sz, p))

    total = sum(v[1] for v in by_ext.values())
    print(f"Root: {root}")
    print(f"Total: {human(total)}")
    print()
    print(f"{'ext':<14} {'count':>8} {'size':>12} {'%':>6}")
    print("-" * 44)
    for ext, (c, s) in sorted(by_ext.items(), key=lambda x: -x[1][1]):
        pct = (s / total * 100) if total else 0
        print(f"{ext:<14} {c:>8} {human(s):>12} {pct:>5.1f}%")

    print()
    print("Top-15 файлов:")
    for sz, p in sorted(files, reverse=True)[:15]:
        rel = p.relative_to(root)
        print(f"  {human(sz):>10}  {rel}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")