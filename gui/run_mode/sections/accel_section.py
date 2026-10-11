"""
Секция Accelerators.
"""

from __future__ import annotations
from gui.run_mode.sections.base import BaseSection
from gui.run_mode.sections.accel_card import AccelCard


class AccelSection(BaseSection):
    """Секция «Accelerators» с карточками AccelCard."""

    TITLE = "Accelerators"
    KIND = "accelerators"

    def _new_card(self, node=None) -> AccelCard:
        """Фабрика карточек — AccelCard вместо NodeCard."""
        return AccelCard(self.KIND, node)