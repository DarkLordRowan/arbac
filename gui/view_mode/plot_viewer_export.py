"""
Экспорт видимых линий PlotWidget в формат plot_viewer.py (matplotlib).

Зачем:
    В C++-проекте Visir GUI отправлял plot_viewer'у то, что на экране
    предпросмотра. Здесь то же самое: собираем видимые кривые
    (с учётом чекбоксов слоёв), конвертируем в JSON-формат
    plot_viewer'а, сохраняем и (опционально) запускаем plot_viewer.

Формат plot_viewer:
    {
      "grid": {"type": "Normal" | "Symlog", "log_linthresh": float},
      "bounds": {"x_min", "x_max", "y_min", "y_max"},
      "lines": [
        {"name", "x", "y", "color" [R,G,B,A], "width", "style",
         "marker", "marker_size", "visible"}, ...
      ]
    }

    y — в display-пространстве. Для Symlog это symlog-преобразованные
    значения; formatter plot_viewer'а восстановит реальные для подписей.
"""

from __future__ import annotations
import json
import math
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt


#: Qt.PenStyle → строка для plot_viewer.
_PEN_STYLE_MAP = {
    Qt.PenStyle.SolidLine: "Solid",
    Qt.PenStyle.DashLine: "Dashed",
    Qt.PenStyle.DotLine: "Dotted",
    Qt.PenStyle.DashDotLine: "Dash-Dot",
    Qt.PenStyle.DashDotDotLine: "Dash-Dot",
}


def _hex_to_rgba255(hex_color: str) -> list[int]:
    """
    '#4a90e2' → [74, 144, 226, 255].
    """
    s = hex_color.lstrip("#")
    if len(s) == 6:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return [r, g, b, 255]
    if len(s) == 8:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        a = int(s[6:8], 16)
        return [r, g, b, a]
    return [128, 128, 128, 255]


def _finite(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _pair_xy(xs: list, ys: list) -> tuple[list, list]:
    """
    Возвращает пары (x, y), отбрасывая точки с нечисловыми или
    нефинитными y (NaN, inf) — plot_viewer'у они не нужны.
    """
    px, py = [], []
    for x, y in zip(xs, ys):
        if not _finite(y):
            continue
        px.append(float(x))
        py.append(float(y))
    return px, py


def build_plot_viewer_data(
    *,
    scale: str,
    symlog_linthresh: float,
    lines: list[dict],
) -> dict:
    """
    Собирает JSON для plot_viewer.

    Принимает:
        scale            — "linear" | "symlog" (log не поддерживается).
        symlog_linthresh — порог symlog (используется только при scale="symlog").
        lines            — список словарей из BasePlotTab._exported_lines.
                            Каждый: {xs, ys_real, ys_plot, label, color,
                                     width, style (Qt.PenStyle), line_item}.

    Возвращает:
        dict для json.dump.
    """
    out_lines = []
    x_min = x_max = None
    y_min = y_max = None

    for rec in lines:
        item = rec.get("line_item")
        try:
            if item is not None and not item.isVisible():
                continue
        except Exception:
            pass

        ys_use = rec["ys_plot"] if scale == "symlog" else rec["ys_real"]
        px, py = _pair_xy(rec["xs"], ys_use)
        if not px:
            continue

        out_lines.append({
            "name": rec["label"],
            "x": px,
            "y": py,
            "color": _hex_to_rgba255(rec["color"]),
            "width": float(rec.get("width", 2)),
            "style": _PEN_STYLE_MAP.get(rec.get("style"), "Solid"),
            "marker": "None",
            "marker_size": 6,
            "visible": True,
        })

        for x in px:
            if x_min is None or x < x_min:
                x_min = x
            if x_max is None or x > x_max:
                x_max = x
        for y in py:
            if y_min is None or y < y_min:
                y_min = y
            if y_max is None or y > y_max:
                y_max = y

    if x_min is None:
        x_min, x_max = 0.0, 100.0
    if y_min is None:
        y_min, y_max = -1.0, 1.0
    # Небольшой запас, чтобы кривые не прилипали к краям.
    if x_min == x_max:
        x_min, x_max = x_min - 1, x_max + 1
    if y_min == y_max:
        y_min, y_max = y_min - 1, y_max + 1

    grid_type = "Symlog" if scale == "symlog" else "Normal"
    log_linthresh = (
        math.log10(symlog_linthresh) if scale == "symlog" else -10.0
    )

    return {
        "grid": {"type": grid_type, "log_linthresh": log_linthresh},
        "bounds": {
            "x_min": x_min, "x_max": x_max,
            "y_min": y_min, "y_max": y_max,
        },
        "lines": out_lines,
    }


def save_to_json(data: dict, path: Path) -> None:
    """Атомарно пишет JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def find_plot_viewer() -> Path | None:
    """
    Ищет plot_viewer.py рядом с проектом (в корне или в tools/).
    """
    here = Path(__file__).resolve()
    candidates = [
        # gui/view_mode/plot_viewer_export.py → up to project root
        here.parent.parent.parent / "plot_viewer.py",
        here.parent.parent.parent / "tools" / "plot_viewer.py",
        Path("plot_viewer.py").resolve(),
        Path("tools/plot_viewer.py").resolve(),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def launch_plot_viewer(json_path: Path) -> bool:
    """
    Запускает plot_viewer с сохранённым JSON.

    Возвращает:
        True, если запуск удался.
    """
    viewer = find_plot_viewer()
    if viewer is None:
        return False
    try:
        subprocess.Popen(
            [sys.executable, str(viewer), str(json_path)],
            cwd=str(viewer.parent),
        )
        return True
    except Exception:
        return False