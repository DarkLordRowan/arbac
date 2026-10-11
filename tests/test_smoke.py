"""
Smoke-тесты: всё импортируется, реестр заполнен.

Самый быстрый уровень проверки. Если он падает — остальное
не имеет смысла.
"""

from __future__ import annotations


def test_import_all_plugins():
    """Все пакеты плагинов импортируются без ошибок."""
    import arbacc.series        # noqa: F401
    import arbacc.noise         # noqa: F401
    import arbacc.accelerators  # noqa: F401
    import arbacc.stopping      # noqa: F401
    import arbacc.postprocess   # noqa: F401
    import arbacc.envelopes     # noqa: F401


def test_registry_filled():
    """Реестр содержит как минимум одного представителя каждой категории."""
    from arbacc.core import list_registered
    reg = list_registered()
    for kind in ("series", "noise", "accelerators",
                 "stopping", "postprocess", "envelopes"):
        assert reg.get(kind), f"категория {kind!r} пуста"


def test_all_plugins_instantiable(ctx):
    """
    Каждый зарегистрированный плагин можно создать с default_params.
    """
    from arbacc.core import get, list_registered
    reg = list_registered()
    for kind in ("series", "noise", "accelerators",
                 "stopping", "postprocess", "envelopes"):
        for name in reg[kind]:
            Cls = get(kind, name)
            params = Cls.default_params()
            # Noise требует seed.
            if kind == "noise":
                obj = Cls(params=params, seed=0)
            else:
                obj = Cls(params=params)
            assert obj is not None


def test_backends_available():
    """Хотя бы один backend доступен, и это mpmath."""
    from arbacc.precision import list_backends
    backends = list_backends()
    assert "mpmath" in backends, f"mpmath обязателен, доступны: {backends}"