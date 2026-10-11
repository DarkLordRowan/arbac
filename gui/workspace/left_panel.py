"""
Левая панель Workspace — конструктор конфига.

Зачем:
    Тот же набор секций, что был в RunWindow, но без кнопок управления —
    кнопки переехали в верхнюю панель Workspace.

    Панель эмитит changed() при любом изменении, чтобы Workspace мог
    обновить JSON и (если включён Visualise) запустить предпросмотр.

Как расширять:
    Новая секция — добавь в _build_sections.
"""

from __future__ import annotations
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea

from gui.run_mode.sections import (
    PrecisionSection, SeriesSection, NoiseSection, AccelSection,
    PostprocessSection, EnvelopeSection,
)


class LeftPanel(QWidget):
    """
    Левая панель — Precision + 5 секций.

    Сигналы:
        changed() — что-то изменилось
    """

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppress = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        self.precision = PrecisionSection()
        self.series = SeriesSection()
        self.noise = NoiseSection()
        self.accel = AccelSection()
        self.postprocess = PostprocessSection()
        self.envelope = EnvelopeSection()
        self.sections = [
            self.series, self.noise, self.accel,
            self.postprocess, self.envelope,
        ]

        layout.addWidget(self.precision)
        for s in self.sections:
            layout.addWidget(s)
        layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

        # Подписки.
        self.precision.changed.connect(self._emit)
        for s in self.sections:
            s.changed.connect(self._emit)

    def _emit(self):
        if not self._suppress:
            self.changed.emit()

    def to_config(self, run_id: str = "exp_001", output: str = "out") -> dict:
        """Собирает конфиг из формы."""
        return {
            "run_id": run_id,
            "output": output,
            "precision": self.precision.to_dict(),
            "series": self.series.to_list(),
            "noise": self.noise.to_list(),
            "accelerators": self.accel.to_list(),
            "postprocess": self.postprocess.to_list(),
            "envelopes": self.envelope.to_list(),
        }

    def from_config(self, config: dict) -> None:
        """Загружает конфиг в форму."""
        self._suppress = True
        try:
            if "precision" in config:
                self.precision.from_dict(config["precision"])
            if "series" in config:
                self.series.from_list(config["series"])
            if "noise" in config:
                self.noise.from_list(config["noise"])
            if "accelerators" in config:
                self.accel.from_list(config["accelerators"])
            if "postprocess" in config:
                self.postprocess.from_list(config["postprocess"])
            if "envelopes" in config:
                self.envelope.from_list(config["envelopes"])
        finally:
            self._suppress = False
        self.changed.emit()

    def clear(self) -> None:
        """Очищает всё."""
        self.precision.from_dict({"backend": "mpmath", "dps": 30})
        for s in self.sections:
            s.from_list([])

    def highlight_errors(self, errors: list[str]) -> None:
        """
        Подсвечивает карточки по списку ошибок вида "kind/id: message".

        Принимает:
            errors — список строк из build_plan
        """
        # Сначала сброс подсветки.
        for s in self.sections:
            for card in s._cards():
                card.set_error(False)

        # Затем подсветка по id.
        for err in errors:
            try:
                prefix = err.split(":", 1)[0]
                kind, node_id = prefix.split("/", 1)
            except ValueError:
                continue
            sec = {
                "series": self.series,
                "noise": self.noise,
                "accelerators": self.accel,
                "postprocess": self.postprocess,
                "envelopes": self.envelope,
            }.get(kind)
            if sec is None:
                continue
