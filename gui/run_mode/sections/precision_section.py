"""
Секция Precision — backend, dps, rounding.

backend и rounding поддерживают массивы через запятую:
    backend: "mpmath, arb"
    rounding: "nearest, floor"
plan развернёт их в декартово произведение.
"""

from __future__ import annotations
from typing import Any

from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QComboBox,
)


ROUNDING_MODES = [
    ("nearest", "Ближайшее / центр интервала (по умолчанию)"),
    ("floor", "Вниз, к −∞ (для arb — нижняя граница интервала)"),
    ("ceiling", "Вверх, к +∞ (для arb — верхняя граница интервала)"),
    ("toward_zero", "К нулю (только mpmath)"),
    ("away_from_zero", "От нуля (только mpmath)"),
    ("rad", "Радиус интервала (только arb, для диагностики)"),
]

_ROUNDING_TOOLTIP = (
    "Режим округления.\n"
    "Можно указать несколько через запятую: 'nearest, floor'.\n\n"
    "  mpmath: nearest, floor, ceiling, toward_zero, away_from_zero\n"
    "  arb:    nearest, floor, ceiling, rad\n\n"
    "При списке backend'ов показываются все доступные режимы\n"
    "(объединение). Некорректные комбинации валидатор отметит\n"
    "при Plan/Validate."
)

_BACKEND_TOOLTIP = (
    "Один backend или список через запятую.\n"
    "Пример: 'mpmath, arb'\n"
    "plan развернёт все комбинации с dps и rounding."
)


class PrecisionSection(QGroupBox):
    """Секция precision."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Precision", parent)
        self._suppress = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # --- backend ---
        row1 = QHBoxLayout()
        lbl_b = QLabel("backend:")
        lbl_b.setToolTip(_BACKEND_TOOLTIP)
        row1.addWidget(lbl_b)

        self._backend = QComboBox()
        self._backend.setEditable(True)
        self._backend.addItems(_available_backends())
        # Пошире, чтобы 'mpmath, arb' уместилось.
        self._backend.setMinimumWidth(240)
        self._backend.setToolTip(_BACKEND_TOOLTIP)
        self._backend.currentTextChanged.connect(self._on_backend_changed)
        row1.addWidget(self._backend, stretch=1)
        layout.addLayout(row1)

        # --- dps ---
        row2 = QHBoxLayout()
        lbl_d = QLabel("dps:")
        lbl_d.setToolTip(
            "dps = десятичные значащие цифры.\n"
            "Можно список через запятую: 30, 50, 100."
        )
        row2.addWidget(lbl_d)
        self._dps = QLineEdit("30")
        self._dps.setPlaceholderText("30 или 30, 50, 100")
        self._dps.setToolTip("Количество значащих десятичных цифр.")
        self._dps.textChanged.connect(self._emit_changed)
        row2.addWidget(self._dps)
        layout.addLayout(row2)

        # --- rounding ---
        row3 = QHBoxLayout()
        lbl_r = QLabel("rounding:")
        lbl_r.setToolTip(_ROUNDING_TOOLTIP)
        row3.addWidget(lbl_r)

        self._rounding = QComboBox()
        self._rounding.setEditable(True)
        self._rounding.addItems([name for name, _ in ROUNDING_MODES])
        for i, (_, hint) in enumerate(ROUNDING_MODES):
            self._rounding.setItemData(i, hint, 3)  # Qt.ToolTipRole
        self._rounding.setMinimumWidth(240)
        self._rounding.setToolTip(_ROUNDING_TOOLTIP)
        self._rounding.currentTextChanged.connect(self._emit_changed)
        row3.addWidget(self._rounding, stretch=1)
        layout.addLayout(row3)

    # ------------------------------------------------------------------
    # Backend → пересборка items rounding
    # ------------------------------------------------------------------

    def _on_backend_changed(self, *_):
        self._rebuild_rounding_for_backend()
        self._emit_changed()

    def _rebuild_rounding_for_backend(self) -> None:
        """
        Обновляет items combo-rounding под текущий набор backend'ов.

        Объединение допустимых режимов для всех указанных backend'ов.
        Текущий введённый текст сохраняется (пользователь может
        вписать 'nearest, floor' вручную).
        """
        backends = self._parse_list(self._backend.currentText())
        supported: set[str] = set()
        for b in backends:
            supported.update(_backend_supported_rounding(b))
        if not supported:
            supported = {"nearest", "floor", "ceiling"}

        current = self._rounding.currentText()
        le = self._rounding.lineEdit()
        cursor_pos = le.cursorPosition() if le else 0

        self._rounding.blockSignals(True)
        try:
            self._rounding.clear()
            for name, hint in ROUNDING_MODES:
                if name in supported:
                    self._rounding.addItem(name)
                    idx = self._rounding.count() - 1
                    self._rounding.setItemData(idx, hint, 3)
            self._rounding.setCurrentText(current or "nearest")
        finally:
            self._rounding.blockSignals(False)

        # Восстанавливаем позицию курсора (важно при ручном вводе).
        if le is not None:
            try:
                le.setCursorPosition(min(cursor_pos, len(le.text())))
            except Exception:
                pass

    def _emit_changed(self, *_):
        if not self._suppress:
            self.changed.emit()

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_list(text: str) -> list[str]:
        """Разбирает 'a, b, c' → ['a', 'b', 'c']."""
        return [
            p.strip() for p in text.replace(",", " ").split()
            if p.strip()
        ]

    def to_dict(self) -> dict[str, Any]:
        # backend — строка или список.
        backends = self._parse_list(self._backend.currentText())
        backend_value: Any = (
            backends if len(backends) > 1
            else (backends[0] if backends else "mpmath")
        )

        # dps — int или список.
        dps_parts = self._parse_list(self._dps.text())
        dps: list[int] = []
        for p in dps_parts:
            try:
                dps.append(int(p))
            except ValueError:
                pass
        if not dps:
            dps = [30]
        dps_value: Any = dps if len(dps) > 1 else dps[0]

        out: dict[str, Any] = {
            "backend": backend_value,
            "dps": dps_value,
        }

        # rounding — строка или список; опускаем чистый 'nearest'.
        roundings = self._parse_list(self._rounding.currentText())
        if not roundings:
            roundings = ["nearest"]
        if not (len(roundings) == 1 and roundings[0] == "nearest"):
            out["rounding"] = (
                roundings if len(roundings) > 1 else roundings[0]
            )
        return out

    def from_dict(self, d: dict[str, Any]) -> None:
        self._suppress = True
        try:
            backend = d.get("backend", "mpmath")
            if isinstance(backend, list):
                self._backend.setCurrentText(
                    ", ".join(str(b) for b in backend)
                )
            else:
                idx = self._backend.findText(str(backend))
                if idx >= 0:
                    self._backend.setCurrentIndex(idx)
                else:
                    self._backend.setCurrentText(str(backend))

            dps = d.get("dps", 30)
            if isinstance(dps, list):
                self._dps.setText(", ".join(str(x) for x in dps))
            else:
                self._dps.setText(str(dps))

            self._rebuild_rounding_for_backend()

            r = d.get("rounding", "nearest")
            if isinstance(r, list):
                self._rounding.setCurrentText(", ".join(str(x) for x in r))
            else:
                self._rounding.setCurrentText(str(r))
        finally:
            self._suppress = False
        self.changed.emit()


def _available_backends() -> list[str]:
    """Список зарегистрированных backend'ов."""
    try:
        import arbacc.precision  # noqa: F401
        from arbacc.precision import list_backends
        names = list_backends()
        return names if names else ["mpmath"]
    except Exception:
        return ["mpmath"]


def _backend_supported_rounding(name: str) -> tuple[str, ...]:
    """Какие rounding поддерживает backend."""
    try:
        from arbacc.precision import get_backend
        return get_backend(name).SUPPORTED_ROUNDING
    except Exception:
        return ("nearest", "floor", "ceiling")