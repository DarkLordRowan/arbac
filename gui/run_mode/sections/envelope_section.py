"""
Секция Envelopes.
"""

from __future__ import annotations
from gui.run_mode.sections.base import BaseSection


class EnvelopeSection(BaseSection):
    """Секция «Envelopes»."""

    TITLE = "Envelopes"
    KIND = "envelopes"
    DEFAULT_PARAMS = {
        "window": 11,
        "detrend_window": 11,
        "threshold": 0.5,
        "min_history": 20,
        "run_mode": "after",
        "used_as": "observer",
    }