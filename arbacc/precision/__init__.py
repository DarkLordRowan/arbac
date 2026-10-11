"""
Реестр precision backend'ов с автодискавери.

Зачем:
    Любой файл в этой папке (кроме __init__, base и _*) считается
    backend'ом и автоматически импортируется. Если импорт не удался
    (например, python-flint не установлен) — файл тихо пропускается.

    Каждый backend регистрируется через @register_backend("имя")
    внутри своего модуля.

Правило именования:
    mpmath_backend.py → backend "mpmath"
    arb_backend.py    → backend "arb"
    gmpy2_backend.py  → backend "gmpy2"
    Имя в @register_backend может быть любым, но по традиции
    совпадает с именем файла без суффикса _backend.

Как расширять:
    Создай новый файл xxx_backend.py с классом-наследником
    PrecisionBackend и декоратором @register_backend("xxx").
    Autodiscovery подхватит автоматически.
"""

from __future__ import annotations
import importlib
import pkgutil
from pathlib import Path

from arbacc.precision.base import (
    PrecisionBackend,
    get_backend,
    list_backends,
    register_backend,
)

#: Файлы, которые не являются backend'ами.
_SKIP = {"base", "__init__"}


def _autodiscover() -> None:
    """Импортирует все *_backend.py, чтобы сработал @register_backend."""
    pkg_dir = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_dir)]):
        name = info.name
        if name.startswith("_") or name in _SKIP:
            continue
        try:
            importlib.import_module(f"{__name__}.{name}")
        except ImportError:
            # Библиотека не установлена — backend недоступен.
            pass


_autodiscover()


__all__ = [
    "PrecisionBackend",
    "get_backend",
    "list_backends",
    "register_backend",
]