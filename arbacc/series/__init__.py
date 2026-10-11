"""
Autodiscovery модулей-плагинов для рядов.

Зачем:
    Чтобы @register сработал, модуль с классом должен быть импортирован.
    Здесь мы автоматически импортируем все .py-файлы из этой папки
    (кроме __init__), и регистрация происходит без ручного списка.

Как расширять:
    Просто создай новый файл series/my_series.py с классом и @register —
    он подхватится автоматически. Ничего сюда добавлять не нужно.
"""

from __future__ import annotations
import importlib
import pkgutil
from pathlib import Path

_PKG_DIR = Path(__file__).parent


def _autodiscover() -> None:
    """Импортирует все модули в пакете, чтобы сработали @register."""
    for info in pkgutil.iter_modules([str(_PKG_DIR)]):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{info.name}")


_autodiscover()