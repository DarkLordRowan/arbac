"""
Секция Postprocess.
"""

from __future__ import annotations
from gui.run_mode.sections.base import BaseSection


class PostprocessSection(BaseSection):
    """Секция «Postprocess»."""

    TITLE = "Postprocess"
    KIND = "postprocess"
    DEFAULT_PARAMS = {"window": 5, "passes": 2}