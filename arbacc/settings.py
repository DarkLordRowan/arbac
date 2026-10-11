"""
Глобальные настройки фреймворка.

Зачем:
    Все константы, которые раньше были разбросаны по файлам
    (DEFAULT_N_MAX, max_tasks в GUI, max_dps в preview), — здесь.

    Переопределяются через:
      - settings.json в корне проекта (если есть),
      - переменные окружения ARBACC_*.

Как расширять:
    Добавляй новые константы в соответствующую группу.
"""

from __future__ import annotations
import json
import os
from pathlib import Path


#: Путь к опциональному settings.json.
_SETTINGS_FILE = Path(__file__).parent.parent / "settings.json"


# --- RUNNER ----------------------------------------------------------

#: Default n_max для акселератора.
RUNNER_DEFAULT_N_MAX: int = 1000

#: Default критерии остановки.
RUNNER_DEFAULT_STOPPING: list[dict] = [
    {"type": "max_iter", "params": {"n": 100}},
]

#: Default stopping_mode.
RUNNER_DEFAULT_STOPPING_MODE: str = "any"

#: Хранить каждую N-ю итерацию. 1 = все, 10 = каждая десятая.
#: Последняя итерация ВСЕГДА сохраняется, даже если не попала в шаг.
STORAGE_ITER_STRIDE: int = 1


#: Формат хранения results и streams:
#:   "jsonl"      — обычный JSONL (читаемо, много места)
#:   "jsonl.gz"   — gzip-сжатый JSONL (~5× сжатие, читаемо через zcat)
#:   "parquet"    — Apache Parquet (колоночное, ~10-30× сжатие)
STORAGE_FORMAT: str = "parquet"

#: Компрессия для parquet: "snappy" | "gzip" | "zstd".
STORAGE_PARQUET_COMPRESSION: str = "zstd"

# --- PREVIEW (GUI) ---------------------------------------------------

#: Максимум accel-задач в одном preview.
PREVIEW_MAX_TASKS: int = 20

#: Максимум n_max для preview.
PREVIEW_MAX_N: int = 500

#: Максимум dps для preview.
PREVIEW_MAX_DPS: int = 200

#: Backend для preview. Пусто → из конфига.
PREVIEW_BACKEND: str = "arb"

#: Использовать кэш preview.
PREVIEW_USE_CACHE: bool = True


# --- PARALLEL --------------------------------------------------------

#: Включить многопроцессную обработку.
PARALLEL_ENABLED: bool = False

#: Сколько процессов. 0 → os.cpu_count().
PARALLEL_WORKERS: int = 0

# --- Загрузка --------------------------------------------------------

def _load_settings_file() -> None:
    """Загружает settings.json, если он есть."""
    if not _SETTINGS_FILE.exists():
        return
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return
    g = globals()
    for k, v in data.items():
        if k.startswith("_") or k not in g:
            continue
        if isinstance(g[k], bool) and not isinstance(v, bool):
            continue
        if isinstance(g[k], int) and not isinstance(v, (int, float)):
            continue
        g[k] = v


def _apply_env_overrides() -> None:
    """Переопределяет настройки через ARBACC_* env vars."""
    g = globals()
    for k in list(g.keys()):
        if k.startswith("_") or not k.isupper():
            continue
        env_key = f"ARBACC_{k}"
        if env_key not in os.environ:
            continue
        raw = os.environ[env_key]
        current = g[k]
        try:
            if isinstance(current, bool):
                g[k] = raw.lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int):
                g[k] = int(raw)
            elif isinstance(current, float):
                g[k] = float(raw)
            elif isinstance(current, str):
                g[k] = raw
        except ValueError:
            pass


_load_settings_file()
_apply_env_overrides()


def describe() -> dict:
    """Возвращает все текущие настройки."""
    g = globals()
    return {k: v for k, v in g.items()
            if k.isupper() and not k.startswith("_")}