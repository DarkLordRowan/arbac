"""
Карточка акселератора — с полями n_max, stopping_mode и редактором stopping.
"""

from __future__ import annotations
from PyQt6.QtWidgets import QLabel

from gui.run_mode.sections.card import NodeCard
from gui.run_mode.sections.stopping_editor import StoppingEditor


class AccelCard(NodeCard):
    """Карточка акселератора с доп. полями и stopping-редактором."""

    EXTRA_FIELDS = [
        ("n_max", "n_max:", 100),
        ("stopping_mode", "stopping_mode:", "any"),
    ]

    def _build_extra_body(self, body_layout) -> None:
        """Добавляет редактор stopping после extra-полей."""
        body_layout.addWidget(QLabel(""))
        self._stopping_editor = StoppingEditor()
        self._stopping_editor.changed.connect(self._emit_changed)
        body_layout.addWidget(self._stopping_editor)

    def _extra_to_dict(self, out: dict) -> None:
        """Добавляет stopping в сериализацию."""
        if hasattr(self, "_stopping_editor"):
            criteria = self._stopping_editor.to_list()
            if criteria:
                out["stopping"] = criteria

    def _extra_from_dict(self, node: dict) -> None:
        """Загружает stopping из узла."""
        if hasattr(self, "_stopping_editor"):
            self._stopping_editor.from_list(node.get("stopping", []))