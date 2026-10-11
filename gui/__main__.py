"""
Точка входа GUI для `python -m gui`.

Делегирует в gui.main.main(), чтобы логика была в одном месте.
"""

from __future__ import annotations
import sys

from gui.main import main


if __name__ == "__main__":
    sys.exit(main())