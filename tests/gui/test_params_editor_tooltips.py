"""Проверка, что tooltips реально ставятся на поля."""
from __future__ import annotations
import pytest


@pytest.fixture
def editor(qapp):
    from gui.run_mode.sections.params_editor import ParamsEditor
    ed = ParamsEditor("series", "zeta")
    yield ed
    ed.deleteLater()


def test_zeta_s_has_tooltip(editor):
    """У параметра 's' должен быть tooltip."""
    w = editor._fields.get("s")
    assert w is not None
    assert w.toolTip() != ""


def test_editor_for_enum_has_tooltip(qapp):
    from gui.run_mode.sections.params_editor import ParamsEditor
    # gaussian имеет enum-поле mode.
    ed = ParamsEditor("noise", "gaussian")
    try:
        w = ed._fields.get("mode")
        assert w is not None
        tip = w.toolTip()
        assert tip != ""
        # В tooltip должно быть перечисление значений.
        assert "absolute" in tip or "relative" in tip
    finally:
        ed.deleteLater()

from PyQt6.QtWidgets import QFormLayout


def test_labels_have_no_spec_suffix(editor):
    """
    Метка параметра не должна содержать [...] — вся спека
    перенесена в tooltip.
    """
    layout = editor._outer
    for row in range(layout.rowCount()):
        item = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
        if item is None:
            continue
        w = item.widget()
        if w is None:
            continue
        text = w.text() if hasattr(w, "text") else ""
        assert "[" not in text, f"в метке есть [...]: {text!r}"


def test_all_fields_have_tooltip(editor):
    """Каждое поле параметра имеет непустой tooltip."""
    for name, w in editor._fields.items():
        tip = w.toolTip()
        assert tip, f"у параметра {name!r} нет tooltip"        

from PyQt6.QtWidgets import QFormLayout


def test_labels_have_no_spec_suffix(editor):
    """
    Метка параметра не должна содержать [...] — вся спека
    перенесена в tooltip.
    """
    layout = editor._outer
    for row in range(layout.rowCount()):
        item = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
        if item is None:
            continue
        w = item.widget()
        if w is None:
            continue
        text = w.text() if hasattr(w, "text") else ""
        assert "[" not in text, f"в метке есть [...]: {text!r}"


def test_all_fields_have_tooltip(editor):
    """Каждое поле параметра имеет непустой tooltip."""
    for name, w in editor._fields.items():
        tip = w.toolTip()
        assert tip, f"у параметра {name!r} нет tooltip"        