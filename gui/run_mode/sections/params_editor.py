"""
Виджет редактирования params одного узла.

Особенности:
    - поля с spec["type"] == "enum" — QComboBox;
    - поля с spec["type"] == "file" — QLineEdit + кнопка «…»;
    - остальные — QLineEdit с JSON-парсингом;
    - в метке — только имя параметра (+ '*' для обязательных);
    - вся спецификация (тип, диапазон, значения, default, hint) — в tooltip.
"""

from __future__ import annotations
import json

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QHBoxLayout, QPushButton,
    QFileDialog, QComboBox,
)

from arbacc.core.registry import get


class ParamsEditor(QWidget):
    """Редактор params одного узла."""

    changed = pyqtSignal()

    def __init__(self, kind: str, type_name: str, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._type_name = type_name
        self._fields: dict[str, QWidget] = {}
        self._required: set[str] = set()
        self._defaults: dict = {}
        self._spec: dict = {}

        self._outer = QFormLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(4)

        self._rebuild()

    def _clear(self):
        while self._outer.rowCount() > 0:
            self._outer.removeRow(0)
        self._fields.clear()

    def _rebuild(self):
        self._clear()
        self._required = set()
        self._defaults = {}
        self._spec = {}

        if not self._type_name:
            self._add_hint("(no type selected)")
            return

        try:
            Cls = get(self._kind, self._type_name)
        except KeyError:
            self._add_hint(f"(unknown type: {self._type_name})")
            return

        self._defaults = Cls.default_params() or {}
        self._required = Cls.required_params() or set()
        self._spec = getattr(Cls, "param_spec", lambda: {})() or {}

        all_params = sorted(
            set(self._defaults.keys())
            | self._required
            | set(self._spec.keys())
        )

        if not all_params:
            self._add_hint("(no parameters)")
            return

        for name in all_params:
            self._add_param_row(name)

    def _add_hint(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #888; font-style: italic;")
        self._outer.addRow(lbl)

    def _add_param_row(self, name: str):
        is_required = name in self._required
        spec = self._spec.get(name, {})

        # Метка — только имя (+ '*' для обязательных).
        # Всё остальное — в tooltip.
        label_text = name + (" *" if is_required else "")

        label = QLabel(label_text)
        if is_required:
            label.setStyleSheet("color: #ff9a9a;")

        # --- Tooltip для параметра ---
        tooltip_lines = []
        t = spec.get("type")
        if t:
            tooltip_lines.append(f"тип: {t}")
        if spec.get("min") is not None or spec.get("max") is not None:
            lo = spec.get("min", "−∞")
            hi = spec.get("max", "+∞")
            tooltip_lines.append(f"диапазон: [{lo}, {hi}]")
        if spec.get("values"):
            tooltip_lines.append(
                f"значения: {', '.join(str(v) for v in spec['values'])}"
            )
        if is_required:
            tooltip_lines.append("обязательный")
        if name in self._defaults:
            tooltip_lines.append(f"по умолчанию: {self._defaults[name]}")
        if spec.get("hint"):
            tooltip_lines.append("")
            tooltip_lines.append(spec["hint"])
        tip = "\n".join(tooltip_lines)

        label.setToolTip(tip)

        # --- Выбор виджета по типу ---
        if spec.get("type") == "enum":
            combo = QComboBox()
            values = spec.get("values", []) or []
            combo.addItems([str(v) for v in values])
            current = self._defaults.get(name) or (values[0] if values else "")
            idx = combo.findText(str(current))
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.currentTextChanged.connect(self.changed.emit)
            combo.setToolTip(tip)
            self._outer.addRow(label, combo)
            self._fields[name] = combo
            return

        # QLineEdit для остальных типов.
        edit = QLineEdit()
        if name in self._defaults:
            edit.setText(_format_value(self._defaults[name]))
        if is_required and name not in self._defaults:
            edit.setPlaceholderText("(required)")
        edit.textChanged.connect(self.changed.emit)
        edit.setToolTip(tip)

        if spec.get("type") == "file":
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            row_layout.addWidget(edit, stretch=1)
            btn = QPushButton("…")
            btn.setMaximumWidth(30)
            btn.setToolTip("Выбрать файл")
            btn.clicked.connect(
                lambda _=False, e=edit, n=name: self._on_browse(e, n)
            )
            row_layout.addWidget(btn)
            row.setToolTip(tip)
            self._outer.addRow(label, row)
        else:
            self._outer.addRow(label, edit)

        self._fields[name] = edit

    def _on_browse(self, edit: QLineEdit, name: str):
        spec = self._spec.get(name, {})
        filt = spec.get("filter", "All files (*)")
        path, _ = QFileDialog.getOpenFileName(self, "Choose file", "", filt)
        if path:
            edit.setText(path)

    def set_type(self, kind: str, type_name: str):
        self._kind = kind
        self._type_name = type_name
        self._rebuild()

    def to_dict(self) -> dict:
        """Собирает params. Enum-поля → строка, остальные → JSON."""
        out: dict = {}
        for name, w in self._fields.items():
            if isinstance(w, QComboBox):
                out[name] = w.currentText()
            elif isinstance(w, QLineEdit):
                text = w.text().strip()
                if text == "":
                    continue
                out[name] = _parse_value(text)
        return out

    def from_dict(self, params: dict):
        """Загружает значения в поля (без стирания дефолтов)."""
        for name, w in self._fields.items():
            if name not in params:
                continue
            v = params[name]
            if isinstance(w, QComboBox):
                idx = w.findText(str(v))
                if idx >= 0:
                    w.blockSignals(True)
                    w.setCurrentIndex(idx)
                    w.blockSignals(False)
            elif isinstance(w, QLineEdit):
                w.blockSignals(True)
                w.setText(_format_value(v))
                w.blockSignals(False)


def _format_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False)


def _parse_value(s: str):
    """
    Парсит значение поля.
        1) JSON — если строка валидный JSON,
        2) список чисел через запятую,
        3) строка.
    """
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    if "," in s:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        try:
            return [float(p) for p in parts]
        except ValueError:
            try:
                return [int(p) for p in parts]
            except ValueError:
                pass
    return s