"""
Тесты Run через Workspace: реально запускают RunWorker на минимальном
конфиге и ждут завершения. Без открытия GUI.

Важно: в реальном GUI пользователь перед Run либо строит форму вручную,
либо делает Open (форма загружается содержимым файла). Тесты
воспроизводят этот сценарий через workspace._left_edit.from_config().
"""

from __future__ import annotations
import json
from pathlib import Path

import pytest


@pytest.fixture
def workspace(qapp, no_messagebox):
    from gui.workspace import Workspace
    from gui.workspace.state import AppState
    ws = Workspace(AppState())
    yield ws
    ws.window.close()


@pytest.fixture
def minimal_config_file(tmp_path):
    """Минимальный конфиг, сохранённый на диск."""
    cfg = {
        "run_id": "gui_test",
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
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return p, cfg


def _prepare(workspace, config_file_tuple):
    """Загружает конфиг в форму, как это делает Open."""
    path, cfg = config_file_tuple
    workspace.state.current_config_path = path
    workspace._left_edit.from_config(cfg)
    return cfg


def test_run_button_starts_worker_and_completes(
    workspace, minimal_config_file, qapp,
):
    """
    _on_run запускает RunWorker, поток завершается, кнопка Run
    возвращается в исходное состояние.
    """
    _prepare(workspace, minimal_config_file)

    workspace._btn_run.click()
    assert workspace._run_worker is not None

    finished = workspace._run_worker.wait(60_000)
    assert finished, "RunWorker не завершился за 60 секунд"
    qapp.processEvents()

    assert workspace._btn_run.text() == "Run"
    assert workspace._btn_run.isEnabled()


def test_run_creates_output_and_sets_state(
    workspace, minimal_config_file, qapp,
):
    """После Run state.last_output_root указывает на output, файлы на диске."""
    _prepare(workspace, minimal_config_file)

    workspace._btn_run.click()
    workspace._run_worker.wait(60_000)
    qapp.processEvents()

    # state.last_output_root заполнен и указывает на реальную директорию.
    assert workspace.state.last_output_root is not None
    assert workspace.state.last_output_root.exists(), (
        f"output не создан: {workspace.state.last_output_root}"
    )

    # accel-задача сохранена.
    result_files = list(
        (workspace.state.last_output_root / "accel").rglob("result.json")
    )
    assert len(result_files) == 1, (
        f"ожидалось 1 result.json, найдено {len(result_files)}"
    )


def test_run_bad_config_does_not_crash(
    workspace, qapp, tmp_path, no_messagebox,
):
    """Некорректный конфиг → RunWorker логирует fail, но GUI не падает."""
    bad = tmp_path / "bad.json"
    bad_cfg = {
        "run_id": "bad",
        "output": str(tmp_path / "out_bad"),
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"type": "zeta", "params": {}}],   # нет s
        "noise": [],
        "accelerators": [{"type": "aitken_delta2", "params": {}}],
    }
    bad.write_text(json.dumps(bad_cfg, indent=2), encoding="utf-8")

    workspace.state.current_config_path = bad
    workspace._left_edit.from_config(bad_cfg)

    workspace._btn_run.click()
    workspace._run_worker.wait(60_000)
    qapp.processEvents()

    # Главное — GUI не упал.
    assert workspace._btn_run.isEnabled()

    # Реальное число итераций в файле — не 1, а столько, сколько отработал алгоритм.
    from arbacc.storage import load_iterations
    ids = {
        "series_id": "zeta_s3",
        "noise_id": "none",
        "accel_id": "aitken_delta2_dps30",
    }
    # ids могут отличаться при изменении дефолтов — ищем по дереву.
    rel_root = workspace.state.last_output_root / "accel"
    iter_files = list(rel_root.rglob("iterations.parquet")) \
        or list(rel_root.rglob("iterations.jsonl"))
    assert iter_files, f"нет iterations.* в {rel_root}"
    base = iter_files[0]
    if base.name.endswith(".parquet"):
        base = base.with_suffix("")
    rows = load_iterations(base)
    assert len(rows) >= 20, (
        f"ожидали ≥20 итераций, в файле {len(rows)}"
    )    