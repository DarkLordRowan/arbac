"""
Тесты секции Precision: rounding combobox.
"""

from __future__ import annotations
import pytest


@pytest.fixture
def section(qapp):
    from gui.run_mode.sections.precision_section import PrecisionSection
    s = PrecisionSection()
    yield s
    s.deleteLater()


def test_rounding_combo_exists(section):
    assert section._rounding is not None
    # По умолчанию должен быть nearest.
    assert section._rounding.currentText() == "nearest"


def test_rounding_in_to_dict_when_changed(section):
    section._rounding.setCurrentText("floor")
    d = section.to_dict()
    assert d.get("rounding") == "floor"


def test_rounding_default_not_in_to_dict(section):
    """nearest — дефолт, не попадает в dict."""
    section._rounding.setCurrentText("nearest")
    d = section.to_dict()
    assert "rounding" not in d


def test_backend_switch_updates_rounding_options(section, qapp):
    """Смена backend → фильтрация rounding-опций."""
    section._backend.setCurrentText("mpmath")
    qapp.processEvents()
    mp_modes = [
        section._rounding.itemText(i)
        for i in range(section._rounding.count())
    ]
    # mpmath не поддерживает 'rad'
    assert "rad" not in mp_modes
    assert "nearest" in mp_modes


def test_from_dict_with_rounding(section):
    section.from_dict({
        "backend": "mpmath", "dps": 50, "rounding": "ceiling",
    })
    assert section._rounding.currentText() == "ceiling"

# --- Массивы rounding ---

def test_rounding_array_to_dict(section):
    """Ввод 'nearest, floor' → список в to_dict."""
    section._rounding.setCurrentText("nearest, floor")
    d = section.to_dict()
    assert d.get("rounding") == ["nearest", "floor"]


def test_rounding_array_from_dict(section):
    """from_dict принимает список и отображает через запятую."""
    section.from_dict({
        "backend": "mpmath", "dps": 30,
        "rounding": ["nearest", "ceiling"],
    })
    assert section._rounding.currentText() == "nearest, ceiling"
    assert section.to_dict().get("rounding") == ["nearest", "ceiling"]


def test_rounding_single_string_ok(section):
    section._rounding.setCurrentText("floor")
    assert section.to_dict().get("rounding") == "floor"


def test_rounding_nearest_omitted(section):
    """Чистый 'nearest' не попадает в dict (это дефолт)."""
    section._rounding.setCurrentText("nearest")
    d = section.to_dict()
    assert "rounding" not in d


# --- Совместимость с массивом backend ---

def test_backend_array_shows_union_rounding(section, qapp):
    """backend='mpmath, arb' → в items все 6 режимов."""
    section._backend.setCurrentText("mpmath, arb")
    qapp.processEvents()
    items = [
        section._rounding.itemText(i)
        for i in range(section._rounding.count())
    ]
    # mpmath: nearest, floor, ceiling, toward_zero, away_from_zero
    # arb:    nearest, floor, ceiling, rad
    # union:  все 6
    for r in ("nearest", "floor", "ceiling", "toward_zero",
              "away_from_zero", "rad"):
        assert r in items, f"{r} отсутствует в {items}"


def test_backend_array_preserved_in_dict(section):
    section._backend.setCurrentText("mpmath, arb")
    section._dps.setText("30, 50")
    section._rounding.setCurrentText("nearest, floor")
    d = section.to_dict()
    assert d["backend"] == ["mpmath", "arb"]
    assert d["dps"] == [30, 50]
    assert d["rounding"] == ["nearest", "floor"]    

# --- Массивы rounding ---

def test_rounding_array_to_dict(section):
    """Ввод 'nearest, floor' → список в to_dict."""
    section._rounding.setCurrentText("nearest, floor")
    d = section.to_dict()
    assert d.get("rounding") == ["nearest", "floor"]


def test_rounding_array_from_dict(section):
    """from_dict принимает список и отображает через запятую."""
    section.from_dict({
        "backend": "mpmath", "dps": 30,
        "rounding": ["nearest", "ceiling"],
    })
    assert section._rounding.currentText() == "nearest, ceiling"
    assert section.to_dict().get("rounding") == ["nearest", "ceiling"]


def test_rounding_single_string_ok(section):
    section._rounding.setCurrentText("floor")
    assert section.to_dict().get("rounding") == "floor"


def test_rounding_nearest_omitted(section):
    """Чистый 'nearest' не попадает в dict (это дефолт)."""
    section._rounding.setCurrentText("nearest")
    d = section.to_dict()
    assert "rounding" not in d


# --- Совместимость с массивом backend ---

def test_backend_array_shows_union_rounding(section, qapp):
    """backend='mpmath, arb' → в items все 6 режимов."""
    section._backend.setCurrentText("mpmath, arb")
    qapp.processEvents()
    items = [
        section._rounding.itemText(i)
        for i in range(section._rounding.count())
    ]
    # mpmath: nearest, floor, ceiling, toward_zero, away_from_zero
    # arb:    nearest, floor, ceiling, rad
    # union:  все 6
    for r in ("nearest", "floor", "ceiling", "toward_zero",
              "away_from_zero", "rad"):
        assert r in items, f"{r} отсутствует в {items}"


def test_backend_array_preserved_in_dict(section):
    section._backend.setCurrentText("mpmath, arb")
    section._dps.setText("30, 50")
    section._rounding.setCurrentText("nearest, floor")
    d = section.to_dict()
    assert d["backend"] == ["mpmath", "arb"]
    assert d["dps"] == [30, 50]
    assert d["rounding"] == ["nearest", "floor"]    