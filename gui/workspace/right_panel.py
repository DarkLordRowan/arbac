"""
Правая панель Workspace — QTabWidget с пятью вкладками.

Зачем:
    JSON — текущий конфиг.
    Overview / Residual / Tables — визуализация выбранных задач.
    Analysis — массовый анализ output (export + group by + фильтр).
"""

from __future__ import annotations
from PyQt6.QtWidgets import QTabWidget

from gui.run_mode.json_preview import JsonPreview
from gui.view_mode.tabs import (
    OverviewTab, ResidualTab, TablesTab, AnalysisTab,
)


class RightPanel(QTabWidget):
    """Правая панель с пятью вкладками."""

    def __init__(self, state, parent=None):
        """
        Принимает:
            state  — AppState (прокидывается в AnalysisTab).
            parent — родительский виджет.
        """
        super().__init__(parent)
        self._state = state

        self.json_view = JsonPreview()
        self.overview = OverviewTab()
        self.residual = ResidualTab()
        self.tables = TablesTab()
        self.analysis = AnalysisTab(state)

        self.addTab(self.json_view, "JSON")
        self.addTab(self.overview, "Overview")
        self.addTab(self.residual, "Residual |diff|")
        self.addTab(self.tables, "Tables")
        self.addTab(self.analysis, "Analysis")

    # ------------------------------------------------------------------

    def show_config(self, config: dict) -> None:
        self.json_view.set_config(config)

    def show_data(self, data) -> None:
        self.show_data_list([] if data is None else [data])

    def show_data_list(self, tasks, raw_series=None) -> None:
        raw_series = raw_series or []
        self.overview.show_data_list(tasks, raw_series)
        self.residual.show_data_list(tasks, raw_series)
        self.tables.show_data_list(tasks)

    def set_output_root(self, path) -> None:
        """Прокидывает путь в AnalysisTab."""
        self.analysis.set_output_root(path)