"""CLI --parallel реально идёт через execute_batch."""

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
def multi_config(tmp_path):
    """4 accel-задачи — чтобы параллельность была заметна."""
    cfg = {
        "run_id": "test_cli_parallel",
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [
            {"type": "zeta", "params": {"s": 3}},
            {"type": "zeta", "params": {"s": 4}},
            {"type": "zeta", "params": {"s": 5}},
            {"type": "zeta", "params": {"s": 6}},
        ],
        "noise": [],
        "accelerators": [{
            "type": "aitken_delta2", "params": {},
            "n_max": 100,
            "stopping": [{"type": "max_iter", "params": {"n": 50}}],
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


def test_cli_parallel_all_tasks_done(multi_config, project_root, tmp_path):
    """--parallel N выполняет все задачи, печатает Parallel mode."""
    out = tmp_path / "out_par"
    r = _run_cli(
        project_root,
        ["run", str(multi_config), "--output", str(out), "--parallel", "4"],
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    assert "Parallel mode" in r.stdout, (
        f"CLI не перешёл в параллельный режим. stdout={r.stdout!r}"
    )
    assert "Done: 4" in r.stdout, r.stdout


def test_cli_parallel_results_match_sequential(
    multi_config, project_root, tmp_path,
):
    """Параллельный и последовательный прогоны дают одинаковые task_id."""
    out_seq = tmp_path / "out_seq"
    out_par = tmp_path / "out_par"

    r1 = _run_cli(
        project_root,
        ["run", str(multi_config), "--output", str(out_seq)],
    )
    assert r1.returncode == 0, r1.stderr

    r2 = _run_cli(
        project_root,
        ["run", str(multi_config), "--output", str(out_par),
         "--parallel", "4"],
    )
    assert r2.returncode == 0, r2.stderr

    files_seq = sorted(
        p.relative_to(out_seq)
        for p in (out_seq / "accel").rglob("result.json")
    )
    files_par = sorted(
        p.relative_to(out_par)
        for p in (out_par / "accel").rglob("result.json")
    )
    assert files_seq == files_par
    assert len(files_seq) == 4