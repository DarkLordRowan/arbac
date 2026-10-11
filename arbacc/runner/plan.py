"""
Построение детерминированного плана задач.

Зачем нужен:
    Перед запуском раннер строит полный список задач. План двухуровневый:

      Уровень 1 — задачи акселерации:
        (precision, series, noise, accelerator).
        Акселератор считается один раз. Результат сохраняется.

      Уровень 2 — задачи постобработки:
        (accel_task, postprocess ИЛИ envelope).
        Читают результат акселерации, не пересчитывают его.

    План детерминирован: одинаковый конфиг → одинаковый план.

    id всех узлов строится через node_id (см. runner/id.py) —
    читаемый, одинаковый везде (в путях, task_id, applies_to).

Как расширять:
    Новый уровень (например, препроцессинг) — добавь сюда список
    и обход. Логику id не трогай — она в runner/id.py.
"""

from __future__ import annotations
from typing import Any

from arbacc.core.registry import get
from arbacc.runner.expand import expand_all
from arbacc.runner.id import node_id
from arbacc.runner.scope import matches


#: Значения по умолчанию для акселератора.
from arbacc.settings import (
    RUNNER_DEFAULT_N_MAX as DEFAULT_N_MAX,
    RUNNER_DEFAULT_STOPPING as DEFAULT_STOPPING,
    RUNNER_DEFAULT_STOPPING_MODE as DEFAULT_STOPPING_MODE,
)


def build_plan(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """
    Строит двухуровневый план по конфигу.

    Принимает:
        config — полный JSON-конфиг.

    Возвращает:
        {
            "accel":  [accel_task, ...],
            "post":   [post_task, ...],
            "errors": ["...", ...],
        }
    """
    errors: list[str] = []

    # --- Обязательные секции ---
    if not config.get("precision"):
        errors.append("config has no 'precision' section")
    if not config.get("series"):
        errors.append("config has no 'series' section")
    if not config.get("accelerators"):
        errors.append("config has no 'accelerators' section")
    # noise опциональна — если пусто, подставим implicit none.

    precisions = expand_all([config.get("precision", {})])
    series_list = expand_all(config.get("series", []))

    # Нормализация exact_sum: переносим из верхнего уровня в params.
    for s in series_list:
        if "exact_sum" in s and s["exact_sum"]:
            s.setdefault("params", {})
            if "exact_sum" not in s["params"]:
                s["params"] = dict(s["params"])
                s["params"]["exact_sum"] = s["exact_sum"]

    noise_list = expand_all(config.get("noise", []))
    if not noise_list:
        # Implicit none.
        noise_list = [{
            "type": "none",
            "params": {},
            "seed": 0,
        }]

    accel_list = expand_all(config.get("accelerators", []))
    pp_global = expand_all(config.get("postprocess", []))
    env_global = expand_all(config.get("envelopes", []))

    # --- Фаза 1: предвалидация всех узлов ---
    for kind, nodes in [
        ("series", series_list),
        ("noise", noise_list),
        ("accelerators", accel_list),
        ("postprocess", pp_global),
        ("envelopes", env_global),
    ]:
        for node in nodes:
            _validate_node(kind, node, errors)
            if kind == "accelerators":
                for stop in node.get("stopping", []):
                    _validate_node("stopping", stop, errors)

    # --- Фаза 2: построение задач ---
    accel_tasks: list[dict[str, Any]] = []
    post_tasks: list[dict[str, Any]] = []

    for prec in precisions:
        for series in series_list:
            if not _is_valid("series", series):
                continue
            series_id = node_id("series", series["type"], _params_of(series))

            for noise in noise_list:
                if not _is_valid("noise", noise):
                    continue
                if not matches(noise.get("applies_to"), {"series": series_id}):
                    continue
                noise_id = node_id(
                    "noise", noise["type"], _params_of(noise),
                    extra={"seed": noise.get("seed")},
                )

                for accel in accel_list:
                    if not _is_valid("accelerators", accel):
                        continue
                    if not matches(
                        accel.get("applies_to"),
                        {"series": series_id, "noise": noise_id},
                    ):
                        continue

                    accel_id = node_id(
                        "accelerators", accel["type"], _params_of(accel),
                        extra={
                            "dps": prec.get("dps"),
                            "backend": prec.get("backend"),
                        },
                    )

                    # Strip + дефолты.
                    accel_stripped = _strip(accel, keep_local=True)
                    if "n_max" not in accel_stripped:
                        accel_stripped["n_max"] = DEFAULT_N_MAX
                    if not accel_stripped.get("stopping"):
                        # Дефолт — max_iter(n_max), а не max_iter(100).
                        # Иначе N в GUI никогда не работает больше 100.
                        accel_stripped["stopping"] = [
                            {
                                "type": "max_iter",
                                "params": {"n": int(accel_stripped["n_max"])},
                            }
                        ]
                    if "stopping_mode" not in accel_stripped:
                        accel_stripped["stopping_mode"] = DEFAULT_STOPPING_MODE

                    accel_task = {
                        "kind": "accel",
                        "precision": prec,
                        "series": _strip(series),
                        "noise": _strip(noise),
                        "accelerator": accel_stripped,
                        "ids": {
                            "series_id": series_id,
                            "noise_id": noise_id,
                            "accel_id": accel_id,
                        },
                        "task_id": f"{series_id}__{noise_id}__{accel_id}",
                    }
                    accel_tasks.append(accel_task)

                    # --- Постобработки: глобальные + локальные ---
                    merged_pp = _merge(
                        pp_global,
                        expand_all(accel.get("postprocess", [])),
                        "postprocess",
                    )
                    merged_env = _merge(
                        env_global,
                        expand_all(accel.get("envelopes", [])),
                        "envelopes",
                    )

                    for pp in merged_pp:
                        if not _is_valid("postprocess", pp):
                            continue
                        pp_id = node_id(
                            "postprocess", pp["type"], _params_of(pp),
                            extra={"dps": prec.get("dps")},
                        )
                        post_tasks.append({
                            "kind": "post",
                            "parent_task_id": accel_task["task_id"],
                            "precision": prec,
                            "series": _strip(series),
                            "noise": _strip(noise),
                            "accelerator": accel_stripped,
                            "postprocess": _strip(pp),
                            "envelope": None,
                            "ids": {
                                **accel_task["ids"],
                                "post_id": pp_id,
                                "env_id": None,
                            },
                            "task_id": f"{accel_task['task_id']}__{pp_id}",
                        })

                    for env in merged_env:
                        if not _is_valid("envelopes", env):
                            continue
                        env_id = node_id(
                            "envelopes", env["type"], _params_of(env),
                            extra={"dps": prec.get("dps")},
                        )
                        post_tasks.append({
                            "kind": "post",
                            "parent_task_id": accel_task["task_id"],
                            "precision": prec,
                            "series": _strip(series),
                            "noise": _strip(noise),
                            "accelerator": accel_stripped,
                            "postprocess": None,
                            "envelope": _strip(env),
                            "ids": {
                                **accel_task["ids"],
                                "post_id": None,
                                "env_id": env_id,
                            },
                            "task_id": f"{accel_task['task_id']}__{env_id}",
                        })

    accel_tasks.sort(key=lambda t: t["task_id"])
    post_tasks.sort(key=lambda t: t["task_id"])
    return {"accel": accel_tasks, "post": post_tasks, "errors": errors}


def _validate_node(kind: str, node: dict, errors: list[str]) -> bool:
    """
    Проверяет узел через плагин и добавляет ошибки в errors.

    Принимает:
        kind   — категория.
        node   — узел конфига.
        errors — список ошибок.

    Возвращает:
        True, если валиден.
    """
    try:
        Cls = get(kind, node["type"])
    except KeyError as e:
        errors.append(f"{kind}: unknown type {node.get('type')!r}: {e}")
        return False
    errs = Cls.validate_params(_params_of(node))
    for e in errs:
        errors.append(f"{kind}/{node.get('type', '?')}: {e}")
    return not errs


def _is_valid(kind: str, node: dict) -> bool:
    """Тихая проверка узла (без добавления ошибок)."""
    try:
        Cls = get(kind, node["type"])
    except KeyError:
        return False
    return not Cls.validate_params(_params_of(node))


def _params_of(node: dict[str, Any]) -> dict[str, Any]:
    """Возвращает params из узла."""
    if "params" in node:
        return node["params"]
    return {k: v for k, v in node.items() if k not in ("id", "type", "applies_to")}


def _strip(
    node: dict[str, Any] | None,
    keep_local: bool = False,
) -> dict[str, Any] | None:
    """Убирает служебные поля из узла."""
    if node is None:
        return None
    skip = {"applies_to", "id"}
    if not keep_local:
        skip |= {"postprocess", "envelopes"}
    return {k: v for k, v in node.items() if k not in skip}


def _merge(
    global_list: list[dict[str, Any]],
    local_list: list[dict[str, Any]],
    kind: str,
) -> list[dict[str, Any]]:
    """
    Сливает глобальные и локальные компоненты с дедупом по id.

    Принимает:
        global_list — развёрнутые глобальные.
        local_list  — развёрнутые локальные.
        kind        — категория (для вычисления id).

    Возвращает:
        список уникальных компонентов.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for node in global_list + local_list:
        nid = node_id(kind, node["type"], _params_of(node))
        if nid in seen:
            continue
        seen.add(nid)
        out.append(node)
    return out