"""
Тесты вкладки Tables: точные digits_gained через backend.
"""

from __future__ import annotations
import json
from pathlib import Path

import pytest

from gui.view_mode.data_loader import AccelData


def _make_data(tmp_path: Path, dps: int = 50) -> AccelData:
    """Фейковая AccelData с exact_sum и итерациями."""
    exact_str = "1.2020569031595942853997381615114499907649862923404988817923412"
    d = AccelData(
        task_id="t", series_id="zeta_s3", noise_id="none",
        accel_id="aitken_delta2_dps50",
        path=tmp_path / "accel" / "zeta_s3" / "none" / "aitken_delta2_dps50",
    )
    d.input_payload = {
        "precision": {"backend": "mpmath", "dps": dps},
    }
    d.exact_sum = exact_str
    # Значения разной точности.
    d.iterations = [
        {"k": 0, "n_used": 3, "estimate": "1.1776315789473684210526315789"},
        {"k": 1, "n_used": 5, "estimate": "1.2020407263797313846176573837"},
        {"k": 2, "n_used": 7, "estimate": exact_str},  # точное
    ]
    return d


@pytest.fixture
def tables_tab(qapp):
    from gui.view_mode.tabs.tables import TablesTab
    tab = TablesTab()
    yield tab
    tab.deleteLater()


def test_tables_has_three_subtabs(tables_tab):
    assert tables_tab._sub.count() == 3
    titles = [tables_tab._sub.tabText(i) for i in range(3)]
    assert any("values" in t.lower() for t in titles)
    assert any("errors" in t.lower() for t in titles)
    assert any("events" in t.lower() for t in titles)


def test_values_show_full_estimate(tables_tab, tmp_path):
    data = _make_data(tmp_path)
    tables_tab.show_data_list([data])
    # 3 строки
    assert tables_tab._values.rowCount() == 3

    # Собираем все значения из колонки estimate, независимо от порядка.
    estimates = []
    for i in range(tables_tab._values.rowCount()):
        it = tables_tab._values.item(i, 2)
        assert it is not None, f"estimate пусто в строке {i}"
        estimates.append(it.text())

    # Одно из них — точное (совпадает с exact_sum).
    assert any(e.startswith("1.2020569") for e in estimates), (
        f"нет точного значения среди {estimates}"
    )
    # Одно — приближённое.
    assert any(e.startswith("1.17763") for e in estimates)


def test_errors_digits_precise(tables_tab, tmp_path):
    """
    Для близкого значения (30 знаков) digits_gained должно быть
    заметно больше 15 — доказывает, что используется backend.digits_of,
    а не float.
    """
    data = _make_data(tmp_path, dps=50)
    # Переписываем iterations: k=2 даёт ~30 верных знаков.
    data.iterations = [
        {"k": 0, "n_used": 3, "estimate": "1.20"},
        {"k": 1, "n_used": 5, "estimate": "1.2020569031"},
        {"k": 2, "n_used": 7,
         "estimate": "1.202056903159594285399738161511"},
    ]
    tables_tab.show_data_list([data])
    assert tables_tab._errors.rowCount() == 3

    digits = _collect_digits(tables_tab._errors)
    assert digits, "нет данных в колонке digits"
    assert max(digits) >= 25, (
        f"макс digits={max(digits)}, ожидали ≥ 25. Все: {digits}"
    )


def test_errors_high_dps_not_capped_at_15(tables_tab, tmp_path):
    """
    Регрессия: раньше float(est - exact) обрезал digits_gained
    на ~15. Теперь backend.digits_of — до dps.
    """
    data = _make_data(tmp_path, dps=50)
    data.iterations = [
        {"k": 0, "n_used": 3, "estimate": "1.20"},
        {"k": 1, "n_used": 5, "estimate": "1.2020569031"},
        {"k": 2, "n_used": 7,
         "estimate": "1.202056903159594285399738161511449990764986292"},
    ]
    tables_tab.show_data_list([data])

    digits = _collect_digits(tables_tab._errors)
    assert digits, "нет данных в колонке digits"
    assert max(digits) > 15, (
        f"макс digits={max(digits)}, ожидали >15. Все: {digits}"
    )


def _collect_digits(table) -> list[int]:
    """Собирает все целые значения из колонки digits_gained (индекс 3)."""
    out: list[int] = []
    for i in range(table.rowCount()):
        it = table.item(i, 3)
        if it is None:
            continue
        t = it.text().strip()
        if t.lstrip("-").isdigit():
            out.append(int(t))
    return out