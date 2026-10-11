"""
Редактор списка критериев остановки.

Зачем:
    Акселератор имеет список stopping — каждый критерий это
    {"type": ..., "params": {...}}. Пользователь должен уметь
    добавлять/удалять критерии прямо в карточке, а не через JSON.

    Каждая строка — комбо типа + ParamsEditor + кнопка удаления.

Как расширять:
    Если понадобятся другие вложенные списки (например, локальные
    postprocess/envelopes внутри акселератора), сделай по аналогии.
"""

from __future__ import annotations
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFrame,
)

from arbacc.core.registry import list_registered, get
from gui.run_mode.sections.params_editor import ParamsEditor


class StoppingEditor(QWidget):
    """
    Редактор списка stopping.

    Сигналы:
        changed() — список изменился
    """

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppress = False
        self._rows: list[_StoppingRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>stopping criteria:</b>"))
        header.addStretch()
        btn_add = QPushButton("+ Add criterion")
        btn_add.clicked.connect(self._on_add)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(8, 0, 0, 0)
        self._rows_layout.setSpacing(2)
        layout.addWidget(self._rows_container)

    def to_list(self) -> list[dict]:
        """Возвращает список критериев."""
        return [r.to_dict() for r in self._rows]

    def from_list(self, criteria: list[dict]) -> None:
        """Загружает список критериев."""
        self._suppress = True
        try:
            for row in list(self._rows):
                self._remove_row_widget(row)
            for c in criteria:
                self._add_row(c.get("type", ""), c.get("params", {}))
        finally:
            self._suppress = False
        self.changed.emit()

    def _on_add(self) -> None:
        """Добавляет пустой критерий."""
        types = list_registered("stopping").get("stopping", [])
        default_type = types[0] if types else ""
        self._add_row(default_type, {})
        self.changed.emit()

    def _add_row(self, type_name: str, params: dict) -> None:
        """Добавляет строку критерия."""
        row = _StoppingRow(type_name, params)
        row.changed.connect(self._on_row_changed)
        row.removed.connect(self._on_row_removed)
        self._rows_layout.addWidget(row)
        self._rows.append(row)

    def _remove_row_widget(self, row: "_StoppingRow") -> None:
        """Удаляет строку из layout."""
        self._rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        if row in self._rows:
            self._rows.remove(row)

    def _on_row_changed(self) -> None:
        if not self._suppress:
            self.changed.emit()

    def _on_row_removed(self, row: "_StoppingRow") -> None:
        self._remove_row_widget(row)
        self.changed.emit()


class _StoppingRow(QFrame):
    """
    Одна строка: комбо типа + параметры + кнопка удаления.

    Сигналы:
        changed()
        removed(object)
    """

    changed = pyqtSignal()
    removed = pyqtSignal(object)

    def __init__(self, type_name: str, params: dict, parent=None):
        super().__init__(parent)
        self._suppress = True
        self._params_by_type: dict[str, dict] = {}
        self._current_type = type_name

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #2a2a2a; border: 1px solid #444; "
            "border-radius: 3px; }"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 4)
        outer.setSpacing(2)

        header = QHBoxLayout()
        header.addWidget(QLabel("type:"))
        self._combo = QComboBox()
        self._combo.addItems(list_registered("stopping").get("stopping", []))
        if type_name:
            idx = self._combo.findText(type_name)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
        header.addWidget(self._combo)
        header.addStretch()
        btn_del = QPushButton("×")
        btn_del.setMaximumWidth(28)
        btn_del.clicked.connect(lambda: self.removed.emit(self))
        header.addWidget(btn_del)
        outer.addLayout(header)

        self._params_editor = ParamsEditor("stopping", type_name)
        self._params_editor.changed.connect(self._on_any_change)
        outer.addWidget(self._params_editor)

        self._current_type = self._combo.currentText()
        self._params_editor.set_type("stopping", self._current_type)
        if params:
            self._params_editor.from_dict(params)

        self._combo.currentTextChanged.connect(self._on_type_changed)
        self._suppress = False

    def to_dict(self) -> dict:
        """Возвращает критерий."""
        return {
            "type": self._combo.currentText(),
            "params": self._params_editor.to_dict(),
        }

    def _on_any_change(self) -> None:
        if not self._suppress:
            self.changed.emit()

    def _on_type_changed(self, new_type: str) -> None:
        """Смена типа: сохраняем/восстанавливаем params."""
        if self._suppress or not new_type:
            return
        old_type = self._current_type
        if old_type and old_type != new_type:
            self._params_by_type[old_type] = self._params_editor.to_dict()
        self._current_type = new_type
        self._params_editor.set_type("stopping", new_type)
        cached = self._params_by_type.get(new_type)
        if cached is not None:
            self._params_editor.from_dict(cached)
        self.changed.emit()