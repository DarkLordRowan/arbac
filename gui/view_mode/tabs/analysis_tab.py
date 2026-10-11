"""
Вкладка Analysis — массовый анализ output.

Зачем:
    После Run и export в output лежат all_results.parquet и другие
    сводные файлы. Эта вкладка позволяет:
      - сделать export прямо из GUI,
      - задать группировку и фильтр,
      - увидеть таблицу min/median/mean/max по группам.

    Использует arbacc.analysis.analyze поверх polars. Если polars
    не установлен — покажет понятную ошибку.

Как расширять:
    Новые агрегации и метрики — в arbacc/analysis/analyze.py.
    Здесь только UI.
"""

from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt


#: Предустановленные варианты группировки.
GROUP_BY_PRESETS = [
    "accel_id",
    "series_id,accel_id",
    "noise_id,accel_id",
    "backend",
    "backend,dps",
    "series_id,backend,accel_id",
    "stopped_by",
    "dps",
]


class AnalysisTab(QWidget):
    """Вкладка Analysis с таблицей сводок."""

    def __init__(self, state, parent=None):
        """
        Принимает:
            state  — AppState (для пути к output).
            parent — родительский виджет.
        """
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- Панель пути и экспорта ---
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Output:"))
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("out/exp_001")
        if state.last_output_root:
            self._path_edit.setText(str(state.last_output_root))
        row1.addWidget(self._path_edit, stretch=1)

        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._on_browse)
        row1.addWidget(btn_browse)

        btn_export = QPushButton("Export to parquet")
        btn_export.clicked.connect(self._on_export)
        row1.addWidget(btn_export)
        layout.addLayout(row1)

        # --- Панель группировки и фильтра ---
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Group by:"))
        self._group_combo = QComboBox()
        self._group_combo.setEditable(True)
        self._group_combo.addItems(GROUP_BY_PRESETS)
        row2.addWidget(self._group_combo, stretch=1)

        row2.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText(
            "key=value,key2=value2  (например noise_id=...)"
        )
        row2.addWidget(self._filter_edit, stretch=1)

        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self._on_apply)
        row2.addWidget(btn_apply)
        layout.addLayout(row2)

        # --- Таблица ---
        self._table = QTableWidget(0, 0)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setSortingEnabled(True)
        layout.addWidget(self._table, stretch=1)

        # --- Статус ---
        self._status = QLabel("Готов")
        layout.addWidget(self._status)

    # ------------------------------------------------------------------
    # Обработчики
    # ------------------------------------------------------------------

    def _on_browse(self):
        """Диалог выбора output."""
        path = QFileDialog.getExistingDirectory(
            self, "Choose output directory",
        )
        if path:
            self._path_edit.setText(path)
            self._state.last_output_root = Path(path)

    def _output_root(self) -> Path | None:
        """Возвращает путь из поля или None."""
        s = self._path_edit.text().strip()
        if not s:
            return None
        p = Path(s)
        if not p.exists():
            QMessageBox.warning(self, "Not found", f"Путь не найден: {p}")
            return None
        return p

    def _on_export(self):
        """Запускает arbacc.storage.export.export_all."""
        root = self._output_root()
        if root is None:
            return
        try:
            from arbacc.storage.export import export_all
        except ImportError as e:
            QMessageBox.critical(
                self, "pyarrow missing",
                f"Нужен pyarrow: pip install pyarrow\n{e}",
            )
            return

        self._status.setText("Export…")
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        try:
            stats = export_all(root, None)
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            self._status.setText("Export failed")
            return

        self._status.setText(
            f"Export OK: results={stats['results']}, "
            f"iterations={stats['iterations']}, "
            f"values={stats['values']}, "
            f"envelopes={stats['envelopes']}"
        )

    def _on_apply(self):
        """Читает all_results.parquet, группирует, показывает в таблице."""
        root = self._output_root()
        if root is None:
            return
        results_path = root / "all_results.parquet"
        if not results_path.exists():
            QMessageBox.information(
                self, "No results",
                f"Файл {results_path} не найден. "
                f"Нажми «Export to parquet» сначала.",
            )
            return

        try:
            from arbacc.analysis import analyze
        except ImportError as e:
            QMessageBox.critical(
                self, "polars missing",
                f"Нужен polars: pip install polars\n{e}",
            )
            return

        by_str = self._group_combo.currentText().strip()
        by = [c.strip() for c in by_str.split(",") if c.strip()]
        filter_str = self._filter_edit.text().strip() or None

        try:
            df = analyze(results_path, by=by, filter_str=filter_str)
        except Exception as e:
            QMessageBox.critical(self, "Analyze failed", str(e))
            self._status.setText("Analyze failed")
            return

        self._fill_table(df)
        self._status.setText(
            f"OK: {df.height} строк, {len(df.columns)} колонок"
        )

    def _fill_table(self, df):
        """
        Заполняет QTableWidget из polars.DataFrame.

        Принимает:
            df — polars.DataFrame.
        """
        cols = df.columns
        rows = df.to_dicts()

        self._table.setSortingEnabled(False)
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setRowCount(len(rows))

        for i, r in enumerate(rows):
            for j, c in enumerate(cols):
                v = r.get(c)
                item = QTableWidgetItem("" if v is None else str(v))
                self._table.setItem(i, j, item)

        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def set_output_root(self, path: Path):
        """Обновляет путь и, если есть all_results.parquet, применяет."""
        self._path_edit.setText(str(path))
        self._state.last_output_root = path