"""
Тесты вкладки Analysis: export, analyze, группировка, фильтр.
"""

from __future__ import annotations
import json
from pathlib import Path

import pytest


@pytest.fixture
def analysis_tab(qapp, tmp_path):
    """AnalysisTab с временным output."""
    from gui.view_mode.tabs.analysis_tab import AnalysisTab
    from gui.workspace.state import AppState

    state = AppState()
    tab = AnalysisTab(state)
    yield tab, state
    tab.deleteLater()


def _make_output(tmp_path: Path) -> Path:
    """Создаёт минимальный output с 2 accel-задачами."""
    out = tmp_path / "out"
    for sid, dps in (("zeta_s3", 30), ("zeta_s3", 50)):
        d = out / "accel" / sid / "none" / f"aitken_delta2_dps{dps}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "result.json").write_text(json.dumps({
            "accelerator": "aitken_delta2",
            "params": {},
            "estimate": "1.2020569",
            "n_used": 100,
            "n_max": 1000,
            "stopped_by": "max_iter(100)",
            "status": "ok",
            "digits_gained": dps - 10,
            "meta": {},
        }), encoding="utf-8")
        (d / "manifest.json").write_text(json.dumps({
            "input": {
                "precision": {"backend": "mpmath", "dps": dps},
                "series": {"type": "zeta", "params": {"s": 3}},
                "noise": {"type": "none", "params": {}},
                "accelerator": {"type": "aitken_delta2", "params": {}},
            },
        }), encoding="utf-8")
    return out


def test_analysis_tab_instantiates(analysis_tab):
    tab, state = analysis_tab
    assert tab._path_edit is not None
    assert tab._group_combo is not None
    assert tab._table is not None


def test_set_output_root_updates_path(analysis_tab, tmp_path):
    tab, state = analysis_tab
    out = tmp_path / "some_dir"
    tab.set_output_root(out)
    assert tab._path_edit.text() == str(out)
    assert state.last_output_root == out


def test_export_creates_parquet_files(analysis_tab, tmp_path):
    tab, state = analysis_tab
    out = _make_output(tmp_path)
    tab.set_output_root(out)

    # Нажимаем export напрямую через внутренний обработчик.
    tab._on_export()

    assert (out / "all_results.parquet").exists()
    assert (out / "all_iterations.parquet").exists()
    # В статусе — успех.
    assert "Export OK" in tab._status.text()


def test_apply_fills_table(analysis_tab, tmp_path):
    tab, state = analysis_tab
    out = _make_output(tmp_path)
    tab.set_output_root(out)
    tab._on_export()   # нужен all_results.parquet

    tab._group_combo.setCurrentText("accel_id")
    tab._on_apply()

    # Должны быть 2 строки (aitken_delta2_dps30, _dps50).
    assert tab._table.rowCount() == 2
    assert tab._table.columnCount() >= 5


def test_apply_with_filter(analysis_tab, tmp_path):
    tab, state = analysis_tab
    out = _make_output(tmp_path)
    tab.set_output_root(out)
    tab._on_export()

    tab._filter_edit.setText("dps=30")
    tab._on_apply()

    assert tab._table.rowCount() == 1