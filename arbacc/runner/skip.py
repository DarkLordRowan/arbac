"""
Пропуск уже посчитанных задач.

Зачем нужен:
    При перезапуске раннера после падения (или просто при повторном
    запуске с тем же конфигом) нужно пропустить те задачи, которые
    уже посчитаны и актуальны. Актуальность проверяется по
    input_hash + code_version в manifest.json.

    ВАЖНО: payload для input_hash должен строиться ОДНОЙ функцией —
    build_input_payload. Если строить его в двух местах (при сохранении
    и при проверке), они рано или поздно разойдутся и skip перестанет
    работать. Поэтому execute.py импортирует build_input_payload отсюда.

Как расширять:
    Если понадобится более мягкая проверка (только input_hash без
    code_version) — параметры should_skip.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from arbacc.storage.manifest import build_manifest


def build_input_payload(task: dict[str, Any]) -> dict[str, Any]:
    """
    Строит payload для манифеста из задачи.

    Единственный источник правды для input_hash. Используется и при
    сохранении (execute.py), и при проверке (should_skip).

    Принимает:
        task — задача из плана

    Возвращает:
        словарь payload.
    """
    return {
        "precision": task["precision"],
        "series": task["series"],
        "noise": task["noise"],
        "accelerator": task["accelerator"],
        "postprocess": task.get("postprocess"),
        "envelope": task.get("envelope"),
    }


def expected_manifest(task: dict[str, Any]) -> dict[str, Any]:
    """
    Строит ожидаемый манифест для задачи.

    Принимает:
        task — задача из плана

    Возвращает:
        словарь манифеста.
    """
    return build_manifest(build_input_payload(task))


def should_skip(
    task: dict[str, Any],
    output_root: Path,
    check_code_version: bool = True,
) -> bool:
    """
    Проверяет, посчитана ли задача и актуальна ли она.

    Принимает:
        task               — задача
        output_root        — корень output
        check_code_version — учитывать ли версию кода

    Возвращает:
        True, если задачу можно пропустить.
    """
    ids = task["ids"]
    dir_path = (
        output_root / "accel"
        / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
    )
    result_path = dir_path / "result.json"
    manifest_path = dir_path / "manifest.json"

    if not result_path.exists() or not manifest_path.exists():
        return False

    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    # Задачу не скипаем, если она упала.
    if result.get("status") == "failed":
        return False

    expected = expected_manifest(task)
    if manifest.get("input_hash") != expected.get("input_hash"):
        return False
    if check_code_version and manifest.get("code_version") != expected.get("code_version"):
        return False

    return True

def should_skip_post(
    task: dict[str, Any],
    output_root: Path,
    check_code_version: bool = True,
) -> bool:
    """
    Проверяет, посчитана ли POST-задача.

    ВАЖНО: несколько post-задач (KZ, hilbert, ...) для одной тройки
    (sid, nid, aid) пишут в ОДНУ папку postprocess/<sid>/<nid>/<aid>/
    и перезаписывают общий manifest.json. Поэтому проверять input_hash
    в общем манифесте нельзя — он отражает только ПОСЛЕДНЮЮ записанную
    задачу.

    Признак «посчитано»:
      - существует общий manifest.json (значит, save_postprocess_results
        дошёл до конца — манифест пишется последним),
      - существует summary.json конкретного фильтра/огибающей:
          postprocess → filters/<plugin_name>/summary.json
          envelope    → envelopes/<plugin_name>/summary.json

    Принимает:
        task               — post-задача из плана.
        output_root        — корень output.
        check_code_version — не используется (манифест общий); оставлен
                             для совместимости сигнатуры.

    Возвращает:
        True, если задачу можно пропустить.
    """
    ids = task["ids"]
    dir_path = (
        output_root / "postprocess"
        / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
    )
    if not dir_path.exists():
        return False
    if not (dir_path / "manifest.json").exists():
        return False

    pp = task.get("postprocess")
    if pp is not None:
        name = pp.get("type")
        if not name:
            return False
        return (dir_path / "filters" / name / "summary.json").exists()

    env = task.get("envelope")
    if env is not None:
        name = env.get("type")
        if not name:
            return False
        return (dir_path / "envelopes" / name / "summary.json").exists()

    return False