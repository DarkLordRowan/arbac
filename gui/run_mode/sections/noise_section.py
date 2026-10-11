"""
Секция Noise.
"""

from __future__ import annotations
from gui.run_mode.sections.base import BaseSection


class NoiseSection(BaseSection):
    """Секция «Noise»."""

    TITLE = "Noise"
    KIND = "noise"
    DEFAULT_PARAMS = {"sigma": "1e-6", "mode": "absolute"}