"""
Тесты раннера: expand, scope, plan, id, execute, skip.
"""

from __future__ import annotations
import json
from pathlib import Path
import pytest

from arbacc.runner import (
    expand_node, matches, node_id, build_plan,
    execute_accel, execute_post, should_skip,
)


# --- expand -----------------------------------------------------------------

@pytest.mark.parametrize("node,expected", [
    ({"a": 1}, 1),
    ({"a": [1, 2, 3]}, 3),
    ({"a": [1, 2], "b": [3, 4, 5]}, 6),
    ({"a": {"x": [1, 2]}}, 2),
    ({"applies_to": ["x", "y"], "a": [1, 2]}, 2),
    ({"stopping": [{"type": "x"}, {"type": "y"}]}, 1),
])
def test_expand_node(node, expected):
    """expand_node корректно разворачивает массивы."""
    assert len(expand_node(node)) == expected


# --- scope ------------------------------------------------------------------

def test_matches_all():
    assert matches("all", {"series": "zeta_s3"})
    assert matches(None, {"series": "zeta_s3"})


def test_matches_exact():
    assert matches(["zeta_s3"], {"series": "zeta_s3"})
    assert not matches(["zeta_s5"], {"series": "zeta_s3"})


def test_matches_prefix():
    """Префиксное совпадение: 'zeta' матчит 'zeta_s3'."""
    assert matches(["zeta"], {"series": "zeta_s3"})
    assert matches(["zeta"], {"series": "zeta_s5"})
    assert not matches(["other"], {"series": "zeta_s3"})


# --- id ---------------------------------------------------------------------

def test_node_id_deterministic():
    """node_id детерминирован."""
    ids = {
        node_id("noise", "gaussian", {"sigma": "1e-6"}, {"seed": 42})
        for _ in range(100)
    }
    assert len(ids) == 1


def test_node_id_short():
    """node_id — читаемый, использует short-имена."""
    id_ = node_id("series", "zeta", {"s": 3})
    assert id_ == "zeta_s3"
    id_ = node_id("series", "cos", {"x": 0.6})
    assert id_ == "cos_x0p6"


def test_node_id_with_extra():
    """node_id включает extra (dps, seed)."""
    id_ = node_id("accelerators", "aitken_delta2", {},
                  {"dps": 50, "backend": "mpmath"})
    assert "dps50" in id_
    # mpmath — дефолт, не включается.
    assert "mpmath" not in id_


# --- plan -------------------------------------------------------------------

def test_build_plan_minimal(config_minimal):
    """Минимальный конфиг → 1 accel-задача, 0 post."""
    plan = build_plan(config_minimal)
    assert len(plan["accel"]) == 1
    assert len(plan["post"]) == 0
    assert plan["errors"] == []


def test_build_plan_full(config_full):
    """Полный конфиг: 4 задачи (2 dps × 2 серии, gauss только к zeta)."""
    plan = build_plan(config_full)
    assert plan["errors"] == []
    # Считаем: zeta_s3 × {none, gauss} × {aitken, wynn} = 4
    #        + geom_q0p7 × {none} × {aitken} = 1
    # × 2 dps = 10.
    assert len(plan["accel"]) == 10


def test_build_plan_empty():
    """Пустой конфиг: 3 ошибки (нет precision, series, accelerators)."""
    plan = build_plan({})
    assert len(plan["errors"]) == 3


def test_build_plan_invalid_params():
    """Плохие params → errors, no accel."""
    cfg = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"type": "zeta", "params": {}}],   # нет s
        "noise": [],
        "accelerators": [{"type": "aitken_delta2", "params": {}}],
    }
    plan = build_plan(cfg)
    assert len(plan["accel"]) == 0
    assert any("zeta" in e for e in plan["errors"])


def test_build_plan_implicit_none():
    """Пустая секция noise → implicit none."""
    cfg = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{"type": "aitken_delta2", "params": {}}],
    }
    plan = build_plan(cfg)
    assert len(plan["accel"]) == 1
    assert "none" in plan["accel"][0]["task_id"]


# --- execute + skip ---------------------------------------------------------

def test_execute_and_skip(config_minimal, tmp_output):
    """execute_accel сохраняет, should_skip потом срабатывает."""
    plan = build_plan(config_minimal)
    task = plan["accel"][0]
    assert not should_skip(task, tmp_output)
    r = execute_accel(task, tmp_output)
    assert r["status"] == "ok"
    assert should_skip(task, tmp_output)


def test_execute_creates_files(config_minimal, tmp_output):
    """execute_accel создаёт result.json, iterations.jsonl, manifest.json."""
    plan = build_plan(config_minimal)
    r = execute_accel(plan["accel"][0], tmp_output)
    assert r["status"] == "ok"
    path = tmp_output / "accel" / plan["accel"][0]["ids"]["series_id"] \
        / plan["accel"][0]["ids"]["noise_id"] \
        / plan["accel"][0]["ids"]["accel_id"]
    assert (path / "result.json").exists()
    # Формат iterations зависит от settings.STORAGE_FORMAT.
    iters_files = (
        list(path.glob("iterations.jsonl"))
        + list(path.glob("iterations.jsonl.gz"))
        + list(path.glob("iterations.parquet"))
    )
    assert iters_files, (
        f"no iterations.* file in {path}, содержимое: "
        f"{list(path.iterdir())}"
    )
    assert (path / "manifest.json").exists()