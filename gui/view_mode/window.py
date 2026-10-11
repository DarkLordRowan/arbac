"""
Окно View-режима.

Зачем:
    Позволяет открыть output, выбрать задачу и визуализировать её.
    Три вкладки: Overview, Residual, Tables.

    Слева — список задач (все accel-директории в output).
    Справа — выбранная задача в трёх представлениях.

Как расширять:
    Новые вкладки — добавляй в QTabWidget. Общую навигацию по задачам
    и загрузку данных не трогай.
"""

from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTabWidget, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QSplitter,
)
from PyQt6.QtCore import Qt

from gui.common.state import AppState
from gui.view_mode.data_loader import list_accel_tasks, AccelData
from gui.view_mode.tabs import OverviewTab, ResidualTab, TablesTab


class ViewWindow:
    """Окно View-режима."""

    def __init__(self, state: AppState):
        """
        Принимает:
            state — общее состояние приложения
        """
        self.state = state
        self.window = QMainWindow()
        self.window.setWindowTitle("arbacc — View")
        self.window.resize(1300, 850)

        self._tasks: list[AccelData] = []

        central = QWidget()
        layout = QVBoxLayout(central)

        # Панель открытия.
        top = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Путь к output (например, out/exp_001)")
        if state.last_output_root:
            self._path_edit.setText(str(state.last_output_root))
        btn_browse = QPushButton("Browse…")
        btn_open = QPushButton("Open")
        btn_refresh = QPushButton("Refresh")
        btn_browse.clicked.connect(self._on_browse)
        btn_open.clicked.connect(self._on_open)
        btn_refresh.clicked.connect(self._on_open)
        top.addWidget(QLabel("Output:"))
        top.addWidget(self._path_edit, stretch=1)
        top.addWidget(btn_browse)
        top.addWidget(btn_open)
        top.addWidget(btn_refresh)
        layout.addLayout(top)

        # Splitter: список задач | вкладки.
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая панель — список задач.
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("<b>Задачи</b>"))
        self._task_list = QListWidget()
        self._task_list.currentRowChanged.connect(self._on_task_selected)
        left_layout.addWidget(self._task_list)
        splitter.addWidget(left)

        # Правая панель — вкладки.
        self._tabs = QTabWidget()
        self._overview = OverviewTab()
        self._residual = ResidualTab()
        self._tables = TablesTab()
        self._tabs.addTab(self._overview, "Overview")
        self._tabs.addTab(self._residual, "Residual |diff|")
        self._tabs.addTab(self._tables, "Tables")
        splitter.addWidget(self._tabs)

        splitter.setSizes([300, 1000])
        layout.addWidget(splitter, stretch=1)

        self.window.setCentralWidget(central)

        # Если уже был output — попробуем открыть.
        if state.last_output_root and state.last_output_root.exists():
            self._load_output(state.last_output_root)

    def _on_browse(self):
        """Диалог выбора папки output."""
        path = QFileDialog.getExistingDirectory(
            self.window, "Choose output directory",
        )
        if path:
            self._path_edit.setText(path)
            self._on_open()

    def _on_open(self):
        """Открывает output по пути из поля."""
        path_str = self._path_edit.text().strip()
        if not path_str:
            QMessageBox.warning(self.window, "No path", "Укажи путь к output.")
            return
        path = Path(path_str)
        if not path.exists():
            QMessageBox.warning(self.window, "Not found", f"Путь не найден: {path}")
            return
        self.state.last_output_root = path
        self._load_output(path)

    def _load_output(self, output_root: Path):
        """Сканирует output и заполняет список задач."""
        tasks = list_accel_tasks(output_root)
        self._tasks = tasks
        self._task_list.clear()
        if not tasks:
            self._task_list.addItem(
                QListWidgetItem("(нет задач — проверь, что accel/ не пуст)")
            )
            return
        for t in tasks:
            item = QListWidgetItem(t.short_label)
            item.setToolTip(f"task_id={t.task_id}\npath={t.path}")
            self._task_list.addItem(item)

    def _on_task_selected(self, row: int):
        """Обновляет вкладки при выборе задачи."""
        if row < 0 or row >= len(self._tasks):
            return
        data = self._tasks[row]
        self._overview.show_data(data)
        self._residual.show_data(data)
        self._tables.show_data(data)

    def show(self):
        """Показывает окно."""
        self.window.show()