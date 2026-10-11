"""
Секция Series.
"""

from __future__ import annotations
from gui.run_mode.sections.base import BaseSection


class SeriesSection(BaseSection):
    """Секция «Series»."""

    TITLE = "Series"
    KIND = "series"
    DEFAULT_PARAMS = {}