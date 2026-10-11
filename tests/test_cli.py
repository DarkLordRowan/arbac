"""
Тесты CLI: validate, plan, run, --skip-existing, --limit.
"""

from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Корень проекта (на уровень выше tests/)."""
    return Path(__file__).parent.parent.resolve()


@pytest.fixture
def minimal_config(tmp_path, project_root):
    """Сохраняет минимальный конфиг во временную папку."""
    cfg = {
        "run_id": "test_cli",
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
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def _run_cli(project_root: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Запускает CLI в подпроцессе."""
    return subprocess.run(
        [sys.executable, "-m", "arbacc.cli", *args],
        capture_output=True, text=True, cwd=str(project_root),
    )


def test_cli_validate_ok(minimal_config, project_root):
    """validate на валидном конфиге → rc=0."""
    r = _run_cli(project_root, ["validate", str(minimal_config)])
    assert r.returncode == 0, f"stderr={r.stderr}"


def test_cli_validate_bad(project_root, tmp_path):
    """validate на плохом конфиге → rc!=0."""
    bad = tmp_path / "bad.json"
    bad.write_text('{"series": []}', encoding="utf-8")
    r = _run_cli(project_root, ["validate", str(bad)])
    assert r.returncode != 0


def test_cli_plan(minimal_config, project_root, tmp_path):
    """plan создаёт plan.jsonl."""
    out = tmp_path / "out_plan"
    r = _run_cli(project_root,
                 ["plan", str(minimal_config), "--output", str(out)])
    assert r.returncode == 0, f"stderr={r.stderr}"
    assert (out / "plan.jsonl").exists()


def test_cli_run(minimal_config, project_root, tmp_path):
    """run выполняет задачу, создаёт progress.json."""
    out = tmp_path / "out_run"
    r = _run_cli(project_root,
                 ["run", str(minimal_config), "--output", str(out)])
    assert r.returncode == 0, f"stderr={r.stderr}"
    assert (out / "progress.json").exists()


def test_cli_run_skip_existing(minimal_config, project_root, tmp_path):
    """--skip-existing скипает посчитанное."""
    out = tmp_path / "out_skip"
    _run_cli(project_root, ["run", str(minimal_config), "--output", str(out)])
    r = _run_cli(project_root,
                 ["run", str(minimal_config), "--output", str(out),
                  "--skip-existing"])
    assert r.returncode == 0, r.stderr
    # В последовательном режиме печатается "SKIP  task_id",
    # в параллельном — "Skipped: N" в итоговой строке.
    assert ("SKIP" in r.stdout) or ("Skipped: 1" in r.stdout), (
        f"skip_existing не сработал. stdout={r.stdout!r}"
    )