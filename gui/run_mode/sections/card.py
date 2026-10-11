"""
Карточка одного узла конфига.

Зачем:
    Отображает один узел (series / noise / accelerator / ...):
      - сворачиваемый заголовок: стрелка, type, Dup, ×,
      - раскрываемое тело: дополнительные поля (n_max, stopping_mode)
        и редактор параметров.

    id генерируется автоматически из type + params — поле id в UI
    отсутствует, пользователь на него не влияет.

    При смене типа параметры кэшируются — если пользователь вернётся
    к прежнему типу, введённые значения восстановятся.

Как расширять:
    Если понадобится превью (первые 5 значений ряда), добавь его в
    раскрываемое тело.
"""

from __future__ import annotations
import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
    QPushButton, QLabel, QFormLayout, QWidget, QToolButton,
)

from arbacc.core.registry import list_registered
from gui.run_mode.sections.params_editor import ParamsEditor


class NodeCard(QGroupBox):
    """
    Карточка одного узла.

    Сигналы:
        changed()           — что-то изменилось
        removed(object)     — нажата Remove (×)
        duplicated(object)  — нажата Duplicate (Dup)
    """

    changed = pyqtSignal()
    removed = pyqtSignal(object)
    duplicated = pyqtSignal(object)

    #: Дополнительные поля узла вне params: [(name, label, default), ...].
    EXTRA_FIELDS: list[tuple[str, str, object]] = []

    def __init__(self, kind: str, node: dict | None = None, parent=None):
        """
        Принимает:
            kind   — "series" | "noise" | ...
            node   — начальные данные узла (или None)
            parent — родительский виджет
        """
        super().__init__(parent)
        self._kind = kind
        self._suppress = True
        self._params_by_type: dict[str, dict] = {}
        self._extra_edits: dict[str, QLineEdit] = {}
        self._current_type: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        # --- Заголовок: стрелка, type, кнопки ---
        header = QHBoxLayout()
        header.setSpacing(4)

        self._toggle = QToolButton()
        self._toggle.setCheckable(True)
        self._toggle.setChecked(True)
        self._toggle.setArrowType(Qt.ArrowType.DownArrow)
        self._toggle.setAutoRaise(True)
        self._toggle.clicked.connect(self._on_toggle)
        header.addWidget(self._toggle)

        header.addWidget(QLabel("type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(_available_types(kind))
        header.addWidget(self._type_combo)

        header.addStretch()
        btn_dup = QPushButton("Dup")
        btn_dup.setMaximumWidth(50)
        btn_del = QPushButton("×")
        btn_del.setMaximumWidth(28)
        btn_dup.clicked.connect(lambda: self.duplicated.emit(self))
        btn_del.clicked.connect(lambda: self.removed.emit(self))
        header.addWidget(btn_dup)
        header.addWidget(btn_del)
        layout.addLayout(header)
        # Отображаемая метка карточки (id генерируется в plan).
        self._label = QLabel("")
        self._label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self._label)

        # --- Тело (сворачиваемое) ---
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(20, 2, 2, 2)
        body_layout.setSpacing(4)

        # Дополнительные поля (n_max, stopping_mode и т.д.).
        if self.EXTRA_FIELDS:
            extra_form = QFormLayout()
            extra_form.setContentsMargins(0, 0, 0, 0)
            extra_form.setSpacing(4)
            for name, label_text, default in self.EXTRA_FIELDS:
                edit = QLineEdit()
                edit.setText(str(default) if default is not None else "")
                edit.textChanged.connect(self._emit_changed)
                lbl = QLabel(label_text)
                tooltip = _extra_field_tooltip(name)
                if tooltip:
                    lbl.setToolTip(tooltip)
                    edit.setToolTip(tooltip)
                extra_form.addRow(lbl, edit)
                self._extra_edits[name] = edit
            body_layout.addLayout(extra_form)
            # Хук: подклассы могут добавить свой контент.
            self._build_extra_body(body_layout)

        # Редактор параметров.
        self._params_editor = ParamsEditor(kind, "")
        self._params_editor.changed.connect(self._emit_changed)
        body_layout.addWidget(self._params_editor)

        layout.addWidget(self._body)

        # Инициализация типа.
        self._current_type = self._type_combo.currentText()
        self._params_editor.set_type(kind, self._current_type)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)

        # Загружаем данные, если есть.
        if node is not None:
            self._load_node(node)

        self._suppress = False
        self._update_label()

    def _update_label(self):
        """Обновляет отображаемую метку по текущим type/params."""
        try:
            self._label.setText(self.display_label())
        except Exception:
            self._label.setText("")

    # ---------- Публичное API ----------

    def to_dict(self) -> dict:
        """
        Возвращает узел для JSON.

        id НЕ включается — он вычисляется в plan.py ПОСЛЕ развёртки
        массивов. Это позволяет одной карточке с x=[0.6, 1] дать две
        задачи с разными id.
        """
        out: dict = {
            "type": self._type_combo.currentText(),
            "params": self._params_editor.to_dict(),
        }
        for name, edit in self._extra_edits.items():
            text = edit.text().strip()
            if text == "":
                continue
            out[name] = _parse_value(text)
        self._extra_to_dict(out)
        return out

    def display_label(self) -> str:
        """
        Человекочитаемая метка карточки: "type (k=v, k2=v2)".

        Показывается рядом с combo типа. Для массивов использует
        сокращённую запись.
        """
        type_name = self._type_combo.currentText()
        params = self._params_editor.to_dict() or {}
        parts = []
        for k in sorted(params.keys()):
            if k in ("exact_sum", "n_raw"):
                continue
            v = params[k]
            if isinstance(v, list):
                inner = ",".join(_short(x) for x in v[:3])
                if len(v) > 3:
                    inner += "…"
                parts.append(f"{k}=[{inner}]")
            else:
                parts.append(f"{k}={_short(v)}")
        if not parts:
            return type_name
        return f"{type_name} ({', '.join(parts)})"

    # ---------- Хуки для подклассов ----------

    def _build_extra_body(self, body_layout) -> None:
        """Хук: подклассы могут добавить свой контент в тело карточки."""
        pass

    def _extra_to_dict(self, out: dict) -> None:
        """Хук: подклассы добавляют свои поля в сериализацию."""
        pass

    def _extra_from_dict(self, node: dict) -> None:
        """Хук: подклассы загружают свои поля из узла."""
        pass

    def set_error(self, has_error: bool) -> None:
        """Подсвечивает карточку при ошибке валидации."""
        if has_error:
            self.setStyleSheet(
                "QGroupBox { border: 1px solid #c44; border-radius: 4px; }"
            )
        else:
            self.setStyleSheet("")

    # ---------- Внутренние ----------

    def _load_node(self, node: dict) -> None:
        """
        Загружает узел в карточку.

        Принимает:
            node — {id, type, params, ...}

        Возвращает:
            None.
        """
        self._suppress = True
        try:
            t = node.get("type", "")
            if t:
                self._type_combo.blockSignals(True)
                try:
                    idx = self._type_combo.findText(t)
                    if idx >= 0:
                        self._type_combo.setCurrentIndex(idx)
                    else:
                        self._type_combo.addItem(t)
                        self._type_combo.setCurrentIndex(
                            self._type_combo.count() - 1
                        )
                finally:
                    self._type_combo.blockSignals(False)

            self._current_type = self._type_combo.currentText()
            self._params_editor.set_type(self._kind, self._current_type)
            self._params_editor.from_dict(node.get("params", {}))
            self._params_by_type[self._current_type] = node.get("params", {})

            # Extra-поля.
            for name, edit in self._extra_edits.items():
                v = node.get(name, "")
                edit.blockSignals(True)
                try:
                    edit.setText(str(v) if v != "" else "")
                finally:
                    edit.blockSignals(False)

            # Хук: подклассы загружают своё (например, stopping).
            self._extra_from_dict(node)
        finally:
            self._suppress = False

    def _emit_changed(self, *_):
        if not self._suppress:
            self._update_label()
            self.changed.emit()

    def _on_toggle(self):
        """Сворачивает / разворачивает тело карточки."""
        visible = self._toggle.isChecked()
        self._body.setVisible(visible)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow
        )

    def _on_type_changed(self, new_type: str):
        """
        Смена типа: сохраняем params старого типа, восстанавливаем
        params нового типа (если были).

        Принимает:
            new_type — новое имя типа.

        Возвращает:
            None.
        """
        if self._suppress or not new_type:
            return
        old_type = self._current_type
        if old_type and old_type != new_type:
            self._params_by_type[old_type] = self._params_editor.to_dict()
        self._current_type = new_type
        self._params_editor.set_type(self._kind, new_type)
        cached = self._params_by_type.get(new_type)
        if cached is not None:
            self._params_editor.from_dict(cached)
        self.changed.emit()


def _available_types(kind: str) -> list[str]:
    """Список доступных типов для категории."""
    reg = list_registered(kind)
    return reg.get(kind, [])


def _parse_value(s: str):
    """Парсит значение extra-поля: JSON, иначе — строка."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


def _extra_field_tooltip(name: str) -> str:
    """Возвращает подсказку для extra-поля по имени."""
    return {
        "n_max": "Максимальное число членов, до которого работает акселератор. "
                 "Целое число. По умолчанию 100.",
        "stopping_mode": "any — остановиться при первом сработавшем критерии; "
                         "all — при всех. Впиши any или all.",
    }.get(name, "")

def _short(v) -> str:
    """Короткое представление значения для метки."""
    if isinstance(v, float):
        return f"{v:g}"
    s = str(v)
    return s if len(s) <= 10 else s[:10] + "…"

