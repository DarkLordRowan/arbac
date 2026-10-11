"""
Autodiscovery модулей-плагинов для акселераторов.

Принцип тот же, что у series/ и noise/.
"""

from __future__ import annotations
import importlib
import pkgutil
from pathlib import Path

_PKG_DIR = Path(__file__).parent


def _autodiscover() -> None:
    for info in pkgutil.iter_modules([str(_PKG_DIR)]):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{info.name}")


_autodiscover()