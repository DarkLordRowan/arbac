"""Тесты параллельного выполнения задач (execute_batch)."""

from __future__ import annotations
import json
from pathlib import Path
import pytest

from arbacc.runner import build_plan
from arbacc.runner.execute import execute_accel
from arbacc.runner.execute_batch import execute_batch


@pytest.fixture
def batch_config():
    """Конфиг с 2 задачами — чтобы было что параллелить."""
    return {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [
            {"type": "zeta", "params": {"s": 3}},
            {"type": "zeta", "params": {"s": 4}},
        ],
        "noise": [],
        "accelerators": [{
            "type": "aitken_delta2", "params": {},
            "n_max": 50,
            "stopping": [{"type": "max_iter", "params": {"n": 20}}],
        }],
    }


def test_execute_batch_all_ok(batch_config, tmp_path):
    """execute_batch выполняет все задачи, возвращает статистику."""
    plan = build_plan(batch_config)
    out = tmp_path / "out"

    stats = execute_batch(
        {"accel": plan["accel"], "post": plan["post"]},
        out,
        workers=2,
    )
    assert stats["accel_ok"] == len(plan["accel"])
    assert stats["accel_failed"] == 0
    assert stats["post_ok"] == 0
    assert stats["elapsed"] > 0
    assert (out / "progress.json").exists()


def test_execute_batch_creates_results(batch_config, tmp_path):
    """После execute_batch есть result.json для каждой задачи."""
    plan = build_plan(batch_config)
    out = tmp_path / "out"
    execute_batch({"accel": plan["accel"], "post": []}, out, workers=2)

    for task in plan["accel"]:
        ids = task["ids"]
        result = (
            out / "accel"
            / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
            / "result.json"
        )
        assert result.exists(), f"нет result.json для {task['task_id']}"


def test_execute_batch_matches_sequential(batch_config, tmp_path):
    """Параллельный и последовательный режимы дают те же status."""
    plan = build_plan(batch_config)

    out_p = tmp_path / "par"
    execute_batch({"accel": plan["accel"], "post": []}, out_p, workers=2)

    out_s = tmp_path / "seq"
    out_s.mkdir()
    for task in plan["accel"]:
        execute_accel(task, out_s)

    for task in plan["accel"]:
        ids = task["ids"]
        rel = (
            Path("accel") / ids["series_id"] / ids["noise_id"]
            / ids["accel_id"] / "result.json"
        )
        rp = out_p / rel
        rs = out_s / rel
        assert rp.exists() and rs.exists()
        dp = json.loads(rp.read_text())
        ds = json.loads(rs.read_text())
        assert dp["status"] == ds["status"], f"{task['task_id']}"