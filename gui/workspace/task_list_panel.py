"""
Левая панель Analysis-режима — список задач из output.

Зачем:
    В Analysis-режиме пользователь не конструирует конфиг, а выбирает
    задачу из уже посчитанного output и визуализирует её.

    Панель эмитит task_selected(AccelData) при выборе задачи.

Как расширять:
    Можно добавить фильтры по series_id, search по имени и т.д.
"""

from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout,
)

from gui.view_mode.data_loader import list_accel_tasks, AccelData


class TaskListPanel(QWidget):
    """
    Панель выбора задачи из output.

    Сигналы:
        task_selected(AccelData)
    """

    task_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[AccelData] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        layout.addWidget(QLabel("<b>Output</b>"))
        row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("out/exp_001")
        btn = QPushButton("Open")
        btn.setMaximumWidth(70)
        btn.clicked.connect(self._on_open)
        row.addWidget(self._path_edit, stretch=1)
        row.addWidget(btn)
        layout.addLayout(row)

        layout.addWidget(QLabel("Задачи:"))
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selected)
        layout.addWidget(self._list)

    def load_from(self, output_root: Path) -> None:
        """Загружает список задач из output."""
        self._path_edit.setText(str(output_root))
        self._tasks = list_accel_tasks(output_root)
        self._list.clear()
        if not self._tasks:
            self._list.addItem(QListWidgetItem("(нет задач)"))
            return
        for t in self._tasks:
            item = QListWidgetItem(t.short_label)
            item.setToolTip(f"task_id={t.task_id}\npath={t.path}")
            self._list.addItem(item)
        # Автовыбор первой.
        if self._tasks:
            self._list.setCurrentRow(0)

    def _on_open(self):
        """Открыть output из поля."""
        p = Path(self._path_edit.text().strip())
        if not p.exists():
            return
        self.load_from(p)

    def _on_selected(self, row: int):
        """Обработчик выбора задачи."""
        if row < 0 or row >= len(self._tasks):
            return
        self.task_selected.emit(self._tasks[row])