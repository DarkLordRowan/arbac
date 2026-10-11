"""
Общие цвета, стили и метки для вкладок Overview и Residual.

Зачем:
    Overview и Residual используют одни и те же цвета для одной и
    той же accel-ветки. Метки (a:, f:, e:, s:) тоже одинаковы.

Как расширять:
    Новый цвет → добавь в COLORS.
    Новый стиль линии → добавь в FILTER_STYLES.
    Новая метка → добавь функцию _xxx_label.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt

from gui.view_mode.data_loader import (
    AccelData,
    name_with_params_short,
)


#: Палитра цветов для accel-веток (40 оттенков).
COLORS = [
    # --- основные ---
    "#4a90e2", "#e2685b", "#6fbf73", "#f0c674",
    "#b489d4", "#7ac0d6", "#e08e4b", "#9e6cd6",
    # --- средние ---
    "#5fb8a3", "#d685b8", "#a3c25a", "#d4b26a",
    "#7a9fcf", "#c47a7a", "#8fc87a", "#b8a5d4",
    # --- тёмные ---
    "#c99b6e", "#8fbfd4", "#d47a9c", "#6ba89e",
    "#4a6fa5", "#b85a4a", "#5aa35a", "#c9a54a",
    # --- светлые ---
    "#9a7ac8", "#6ab0c4", "#d67a3a", "#8a5cc4",
    "#5cb890", "#b878a8", "#92b04a", "#c99f5a",
    # --- пастельные ---
    "#7a90c4", "#a89090", "#90b878", "#c4a5b8",
    "#b8a07a", "#84b0c4", "#b8849c", "#88a890",
]

#: Стили линий для фильтров внутри одной accel-ветки.
FILTER_STYLES = [
    Qt.PenStyle.SolidLine,
    Qt.PenStyle.DashLine,
    Qt.PenStyle.DotLine,
    Qt.PenStyle.DashDotLine,
    Qt.PenStyle.DashDotDotLine,
    # + дополнительные из Qt, если доступны
]


# --- Метки для легенды ----------------------------------------------

def series_label(label: str) -> str:
    """Метка сырой серии: 's: <label>'."""
    return f"s: {label}"


def accel_label(data: AccelData) -> str:
    """
    Метка акселератора.

    Формат: 'a: <series> / <noise> / <accel> [backend=..., dps=...]'.
    Backend показывается, если он не mpmath.
    """
    return (
        f"a: {data.series_display} / {data.noise_display} / "
        f"{data.accel_display}{data.dps_suffix}"
    )


def filter_label(
    data: AccelData,
    filter_name: str,
    filter_params: dict,
) -> str:
    """
    Метка фильтра с параметрами.

    Формат: 'f: <series> / <noise> / <accel> [dps=...] / <filter>(params)'.
    """
    display = name_with_params_short(
        "postprocess", filter_name, filter_params
    )
    return (
        f"f: {data.series_display} / {data.noise_display} / "
        f"{data.accel_display}{data.dps_suffix} / {display}"
    )


def envelope_label(
    data: AccelData,
    env_name: str,
    env_params: dict | None = None,
) -> str:
    """
    Метка огибающей с параметрами.

    Формат: 'e: <series> / <noise> / <accel> [dps=...] / <env>(params)'.
    """
    display = name_with_params_short(
        "envelope", env_name, env_params or {}
    )
    return (
        f"e: {data.series_display} / {data.noise_display} / "
        f"{data.accel_display}{data.dps_suffix} / {display}"
    )


def exact_label(label: str) -> str:
    """Метка точной суммы: 'exact: <label>'."""
    return f"exact: {label}"


def residual_prefix(label: str) -> str:
    """Префикс для residual-метки: '|Δ| <label>'."""
    return f"|Δ| {label}"