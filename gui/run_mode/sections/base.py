"""
BaseSection — сворачиваемая секция со списком карточек.

Зачем:
    Каждая секция (series, noise, ...) — вертикальный список карточек.
    Секция сворачивается кликом по заголовку.

    Секция растягивается по содержимому. Никаких фиксированных высот —
    все размеры задаёт содержимое, общий скролл обеспечивает внешний
    QScrollArea в left_panel.py.

    id новых карточек генерируется как "type_p1_p2_..." на основе
    default_params типа — это читаемо и уникально.

Как расширять:
    Для новой секции наследуйся, задай TITLE и KIND.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QToolButton,
)

from arbacc.core.registry import list_registered, get as _registry_get
from gui.run_mode.sections.card import NodeCard


class BaseSection(QWidget):
    """
    Сворачиваемая секция.

    Сигналы:
        changed() — что-то изменилось
    """

    changed = pyqtSignal()

    TITLE: str = "Section"
    KIND: str = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppress = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        # --- Заголовок-кнопка ---
        self._toggle = QToolButton()
        self._toggle.setText(self.TITLE)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(True)
        self._toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._toggle.setArrowType(Qt.ArrowType.DownArrow)
        self._toggle.setStyleSheet(
            "QToolButton { text-align: left; padding: 6px; "
            "background: #3c3f41; border: 1px solid #555; "
            "font-weight: bold; }"
        )
        self._toggle.clicked.connect(self._on_toggle)
        root.addWidget(self._toggle)

        # --- Тело ---
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(8, 4, 8, 4)
        body_layout.setSpacing(2)

        # Контейнер карточек.
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(4)
        self._cards_layout.addStretch()
        body_layout.addWidget(self._cards_container)

        # Кнопка Add — по левому краю.
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        self._btn_add = QPushButton("+ Add")
        self._btn_add.setMaximumWidth(120)
        self._btn_add.clicked.connect(self._on_add)
        btn_row.addWidget(self._btn_add)
        btn_row.addStretch()
        body_layout.addLayout(btn_row)

        root.addWidget(self._body)

    # ---------- Публичное API ----------

    def to_list(self) -> list[dict]:
        """Возвращает список узлов."""
        return [c.to_dict() for c in self._cards()]

    def from_list(self, nodes: list[dict]) -> None:
        """Загружает узлы."""
        self._suppress = True
        try:
            for card in self._cards():
                self._remove_card_widget(card)
            for node in nodes:
                self._add_card(node)
        finally:
            self._suppress = False
        self.changed.emit()

    # ---------- Внутренние ----------

    def _on_toggle(self):
        """Сворачивает / разворачивает тело."""
        visible = self._toggle.isChecked()
        self._body.setVisible(visible)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow
        )

    def _cards(self) -> list[NodeCard]:
        """Возвращает список карточек (без stretch)."""
        out: list[NodeCard] = []
        for i in range(self._cards_layout.count()):
            w = self._cards_layout.itemAt(i).widget()
            if isinstance(w, NodeCard):
                out.append(w)
        return out

    def _new_card(self, node: dict | None = None) -> NodeCard:
        """Фабрика карточек. Переопределяй для подклассов."""
        return NodeCard(self.KIND, node)

    def _add_card(self, node: dict | None = None) -> NodeCard:
        """Создаёт и добавляет карточку."""
        card = self._new_card(node)
        card.changed.connect(self._on_card_changed)
        card.removed.connect(self._on_card_removed)
        card.duplicated.connect(self._on_card_duplicated)
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
        return card

    def _remove_card_widget(self, card: NodeCard) -> None:
        """Удаляет карточку из layout."""
        self._cards_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()

    def _on_card_changed(self):
        if not self._suppress:
            self.changed.emit()

    def _on_card_removed(self, card: NodeCard):
        self._remove_card_widget(card)
        self.changed.emit()

    def _on_add(self):
        """Добавить карточку с типом по умолчанию."""
        types = list_registered(self.KIND).get(self.KIND, [])
        default_type = types[0] if types else ""
        self._add_card({
            "type": default_type,
            "params": {},
        })
        self.changed.emit()

    def _on_card_duplicated(self, card: NodeCard):
        """Дублировать карточку (без id — сгенерится в plan)."""
        d = card.to_dict()
        self._add_card(d)
        self.changed.emit()