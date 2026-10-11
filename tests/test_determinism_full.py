"""
Детерминизм полного прогона: два прогона одного конфига дают
идентичные iterations.
"""

from __future__ import annotations
from pathlib import Path

from arbacc.runner import build_plan, execute_accel
from arbacc.storage import load_iterations


def test_full_run_is_deterministic(config_minimal, tmp_path):
    """Два прогона одного конфига дают идентичные iterations."""
    plan = build_plan(config_minimal)
    task = plan["accel"][0]

    out1 = tmp_path / "run1"
    out1.mkdir()
    out2 = tmp_path / "run2"
    out2.mkdir()

    r1 = execute_accel(task, out1)
    r2 = execute_accel(task, out2)
    assert r1["status"] == "ok", r1.get("error")
    assert r2["status"] == "ok", r2.get("error")

    ids = task["ids"]
    rel = (
        Path("accel") / ids["series_id"] / ids["noise_id"] / ids["accel_id"]
    )
    it1 = load_iterations(out1 / rel / "iterations")
    it2 = load_iterations(out2 / rel / "iterations")

    assert len(it1) == len(it2)
    for a, b in zip(it1, it2):
        assert a["estimate"] == b["estimate"], f"различие на k={a['k']}"