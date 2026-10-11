"""
Секции Run-режима.
"""

from gui.run_mode.sections.precision_section import PrecisionSection
from gui.run_mode.sections.series_section import SeriesSection
from gui.run_mode.sections.noise_section import NoiseSection
from gui.run_mode.sections.accel_section import AccelSection
from gui.run_mode.sections.postprocess_section import PostprocessSection
from gui.run_mode.sections.envelope_section import EnvelopeSection

__all__ = [
    "PrecisionSection", "SeriesSection", "NoiseSection", "AccelSection",
    "PostprocessSection", "EnvelopeSection",
]