"""
Проверка PARAM_SPEC, display_name, format_short_params у всех плагинов.
"""

from __future__ import annotations
import pytest

from arbacc.core import get, list_registered


ALL_KINDS = ["series", "noise", "accelerators",
             "stopping", "postprocess", "envelopes"]


def _all_plugins():
    """Возвращает список (kind, name, class) для всех плагинов."""
    reg = list_registered()
    out = []
    for kind in ALL_KINDS:
        for name in reg[kind]:
            out.append((kind, name, get(kind, name)))
    return out


@pytest.mark.parametrize("kind,name,Cls", _all_plugins())
def test_has_name_and_display(kind, name, Cls):
    """У каждого плагина есть name и get_display_name()."""
    assert Cls.name, f"{kind}/{name}: пустое name"
    assert Cls.get_display_name(), f"{kind}/{name}: пустое display_name"


@pytest.mark.parametrize("kind,name,Cls", _all_plugins())
def test_param_spec_valid(kind, name, Cls):
    """PARAM_SPEC корректно оформлен."""
    spec = Cls.param_spec()
    assert isinstance(spec, dict), f"{kind}/{name}: PARAM_SPEC не dict"
    for pname, pspec in spec.items():
        assert isinstance(pspec, dict), \
            f"{kind}/{name}.{pname}: spec не dict"
        t = pspec.get("type")
        if t == "enum":
            assert pspec.get("values"), \
                f"{kind}/{name}.{pname}: enum без values"
        if "min" in pspec and "max" in pspec:
            assert pspec["min"] <= pspec["max"], \
                f"{kind}/{name}.{pname}: min > max"


@pytest.mark.parametrize("kind,name,Cls", _all_plugins())
def test_default_params_satisfy_required(kind, name, Cls):
    """
    default_params() содержит все required_params().

    Иначе «Add» в GUI создаст невалидный инстанс.
    """
    defaults = Cls.default_params()
    required = Cls.required_params()
    missing = required - set(defaults.keys())
    assert not missing, \
        f"{kind}/{name}: required {missing} не покрыты defaults"


@pytest.mark.parametrize("kind,name,Cls", _all_plugins())
def test_format_short_params_smoke(kind, name, Cls):
    """format_short_params не падает на default_params."""
    defaults = Cls.default_params()
    s = Cls.format_short_params(defaults)
    assert isinstance(s, str)