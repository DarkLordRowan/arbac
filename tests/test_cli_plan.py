"""Тесты CLI plan: не должен запускать задачи."""

from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_root():
    return Path(__file__).parent.parent.resolve()


@pytest.fixture
def minimal_config(tmp_path):
    cfg = {
        "run_id": "test_plan",
        "output": str(tmp_path / "out"),
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{
            "type": "aitken_delta2", "params": {},
            "n_max": 50,
            "stopping": [{"type": "max_iter", "params": {"n": 20}}],
        }],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return p


def _run_cli(project_root, args):
    return subprocess.run(
        [sys.executable, "-m", "arbacc.cli", *args],
        capture_output=True, text=True, cwd=str(project_root),
    )


def test_plan_does_not_run_tasks(minimal_config, project_root, tmp_path):
    """plan НЕ должен создавать progress.json, accel/, errors.log."""
    out = tmp_path / "out_plan"
    r = _run_cli(
        project_root,
        ["plan", str(minimal_config), "--output", str(out)],
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    assert (out / "plan.jsonl").exists()
    assert not (out / "progress.json").exists(), \
        "plan создал progress.json — значит, он запускал задачи"
    assert not (out / "accel").exists(), \
        "plan создал accel/ — значит, он запускал задачи"


def test_plan_writes_plan_jsonl(minimal_config, project_root, tmp_path):
    """plan создаёт корректный plan.jsonl с kind и task_id."""
    out = tmp_path / "out_plan2"
    r = _run_cli(
        project_root,
        ["plan", str(minimal_config), "--output", str(out)],
    )
    assert r.returncode == 0
    lines = (out / "plan.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1
    rec = json.loads(lines[0])
    assert rec["kind"] == "accel"
    assert "task_id" in rec