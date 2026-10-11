"""
Манифест инстанса — метаданные для воспроизводимости и skip_existing.

Зачем:
    При перезапуске раннера мы хотим пропускать уже посчитанное. Для этого
    нужно уметь отвечать на вопрос: "результат в этой папке соответствует
    текущему входу и текущей версии кода?".

    Ответ даётся через манифест, в котором есть:
      - input_hash: sha256 от канонизированного входа
      - code_version: git-хеш или версия пакета
      - deps: версии зависимостей (mpmath, python)
      - created_at: время создания

Как расширять:
    Если понадобится учитывать ещё что-то (например, версию ОС),
    добавь поле в build_manifest.
"""

from __future__ import annotations
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical_json(obj: Any) -> str:
    """
    Канонизирует объект в JSON: сортировка ключей, без пробелов.

    Принимает:
        obj — любой JSON-сериализуемый объект

    Возвращает:
        строку.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def input_hash(payload: dict[str, Any]) -> str:
    """
    Считает sha256 от канонизированного payload.

    Принимает:
        payload — словарь с описанием входа

    Возвращает:
        hex-строку.
    """
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def code_version() -> str:
    """
    Возвращает версию кода: git-хеш, если есть, иначе версию пакета.

    Принимает:
        ничего

    Возвращает:
        строку.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=2,
            cwd=Path(__file__).parent,
        )
        if out.returncode == 0:
            return "git:" + out.stdout.strip()[:12]
    except Exception:
        pass
    try:
        import arbacc
        return f"pkg:{arbacc.__version__}"
    except Exception:
        return "unknown"


def deps_versions() -> dict[str, str]:
    """
    Возвращает версии ключевых зависимостей.

    Принимает:
        ничего

    Возвращает:
        {имя: версия}.
    """
    versions: dict[str, str] = {"python": sys.version.split()[0]}
    try:
        import mpmath
        versions["mpmath"] = mpmath.__version__
    except Exception:
        pass
    versions["platform"] = platform.system()
    return versions


def build_manifest(input_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Строит манифест для инстанса.

    Принимает:
        input_payload — полное описание входа (ряд, шум, акселератор, ...)

    Возвращает:
        словарь манифеста.
    """
    return {
        "input_hash": input_hash(input_payload),
        "code_version": code_version(),
        "deps": deps_versions(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": input_payload,
    }