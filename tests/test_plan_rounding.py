"""
Проверяет, что rounding сохраняется в plan и в input_payload.
"""

from __future__ import annotations

from arbacc.runner import build_plan, build_input_payload


def test_rounding_preserved_in_plan():
    cfg = {
        "precision": {"backend": "mpmath", "dps": 30, "rounding": "floor"},
        "series": [{"type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{"type": "aitken_delta2", "params": {}}],
    }
    plan = build_plan(cfg)
    assert plan["accel"], "нет accel"
    task = plan["accel"][0]
    assert task["precision"]["rounding"] == "floor"


def test_rounding_default_is_nearest():
    cfg = {
        "precision": {"backend": "mpmath", "dps": 30},
        "series": [{"type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{"type": "aitken_delta2", "params": {}}],
    }
    plan = build_plan(cfg)
    task = plan["accel"][0]
    # Нет в конфиге — нет в precision. execute подставит "nearest".
    assert "rounding" not in task["precision"] or \
           task["precision"]["rounding"] == "nearest"


def test_rounding_affects_input_hash():
    """Разный rounding → разный input_hash → разные задачи."""
    base = {
        "series": [{"type": "zeta", "params": {"s": 3}}],
        "noise": [],
        "accelerators": [{"type": "aitken_delta2", "params": {}}],
    }
    cfg_n = {**base, "precision": {"backend": "mpmath", "dps": 30,
                                    "rounding": "nearest"}}
    cfg_f = {**base, "precision": {"backend": "mpmath", "dps": 30,
                                    "rounding": "floor"}}
    plan_n = build_plan(cfg_n)
    plan_f = build_plan(cfg_f)
    h_n = build_input_payload(plan_n["accel"][0])
    h_f = build_input_payload(plan_f["accel"][0])
    assert h_n["precision"] != h_f["precision"]