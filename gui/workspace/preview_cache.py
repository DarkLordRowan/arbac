"""
Кэш preview — сохранение и загрузка результатов одной задачи.

Зачем:
    Preview часто пересчитывает одно и то же: пользователь меняет
    threshold у огибающей, а accel считается заново. Кэш решает это:
    если input_hash уже посчитан — читаем с диска.

    Формат кэша — тот же, что у output: accel/{sid}/{nid}/{aid}/result.json
    и т.д. То есть кэш — это мини-output на одну задачу. Это позволяет
    использовать один и тот же data_loader для чтения.

    Ключ кэша — input_hash, та же функция build_input_payload(task),
    что использует runner.skip. Единый источник правды: если
    skip_existing считает задачу актуальной — кэш валиден.

Где хранится:
    %TEMP%/arbacc_preview_cache/{input_hash}/

    Пользователь может чистить %TEMP% — кэш пересоздастся.

Как расширять:
    Автоочистка по размеру/времени — добавить сюда. Пока нет.
"""

from __future__ import annotations
import hashlib
import json
import tempfile
from pathlib import Path

from arbacc.runner.skip import build_input_payload
from arbacc.storage.manifest import canonical_json


#: Базовая папка кэша.
CACHE_ROOT = Path(tempfile.gettempdir()) / "arbacc_preview_cache"


def task_cache_key(task: dict) -> str:
    """
    Возвращает ключ кэша для задачи.

    Использует build_input_payload — ту же функцию, что runner.skip
    для skip_existing. Единый источник правды.

    Принимает:
        task — задача (accel или post).

    Возвращает:
        hex-строку (sha1).
    """
    payload = build_input_payload(task)
    s = canonical_json(payload)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def task_cache_dir(task: dict) -> Path:
    """
    Возвращает папку кэша для задачи.

    Принимает:
        task — задача.

    Возвращает:
        Path. Папка может не существовать.
    """
    return CACHE_ROOT / task_cache_key(task)


def has_cached(task: dict) -> bool:
    """
    Проверяет, есть ли готовая задача в кэше.

    Признак готовности: result.json существует и status="ok".

    Принимает:
        task — задача.

    Возвращает:
        True, если можно читать из кэша.
    """
    ids = task.get("ids", {})
    sid = ids.get("series_id")
    nid = ids.get("noise_id")
    aid = ids.get("accel_id")
    if not (sid and nid and aid):
        return False

    path = task_cache_dir(task) / "accel" / sid / nid / aid / "result.json"
    if not path.exists():
        return False
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return result.get("status") == "ok"


def clear_cache() -> int:
    """
    Полностью очищает кэш preview.

    Возвращает:
        число удалённых элементов (для отладки).
    """
    if not CACHE_ROOT.exists():
        return 0
    import shutil
    count = len(list(CACHE_ROOT.iterdir()))
    shutil.rmtree(CACHE_ROOT, ignore_errors=True)
    return count


def cache_size_bytes() -> int:
    """
    Возвращает размер кэша в байтах.

    Используется для отображения в GUI (статус-строка).

    Возвращает:
        размер в байтах.
    """
    if not CACHE_ROOT.exists():
        return 0
    total = 0
    for p in CACHE_ROOT.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total