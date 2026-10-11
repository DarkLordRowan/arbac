"""
PluginBase — общий предок всех плагинов arbacc.

Зачем:
    У всех плагинов (series/noise/accelerators/stopping/postprocess/
    envelopes) есть общие вещи:
      - name, display_name,
      - PARAM_SPEC — единый источник правды о параметрах,
      - default_params / required_params / validate_params —
        выводятся из PARAM_SPEC,
      - param_spec() — возвращает BASE_PARAM_SPEC + PARAM_SPEC,
      - format_short_params() — короткая строка для легенд,
      - get_display_name() — короткое имя.

    Всё это — здесь. Каждый плагин объявляет только name,
    display_name, PARAM_SPEC и рабочие методы.

Как расширять:
    Новый плагин = один файл. Внутри:
        @register("accelerators", "my_algo")
        class MyAlgo(AcceleratorBase):
            name = "my_algo"
            display_name = "mya"
            PARAM_SPEC = {"order": {"type": "int", "default": 3,
                                    "short": "o"}}
            def required_input(self, state): ...
            def step(self, source, state, ctx): ...

    Ничего больше менять не нужно — ни в ядре, ни в GUI.

PARAM_SPEC — формат:
    {
        "имя": {
            "type": "int" | "float" | "str" | "enum" | "file",
            "min": ..., "max": ...,          # для чисел
            "values": [...],                 # для enum
            "required": True,                # обязательный
            "default": ...,                  # значение по умолчанию
            "short": "p",                    # короткое имя для легенд
            "short_values": {...},           # короткие значения enum
            "hidden": True,                  # скрыть из легенды
            "hint": "...",                   # подсказка в GUI
        },
    }
"""

from __future__ import annotations
from abc import ABC
from typing import Any

from arbacc.core._short import format_short_params as _format_short


class PluginBase(ABC):
    """
    Общий предок всех плагинов.

    Атрибуты класса (наследники переопределяют):
        name             — стабильный id (в путях output).
        display_name     — короткое имя для легенд. Пусто → name.
        PARAM_SPEC       — специфичные параметры плагина.
        BASE_PARAM_SPEC  — общие для семейства (сливаются).
    """

    #: Стабильный id.
    name: str = "abstract"

    #: Короткое имя для легенд.
    display_name: str = ""

    #: Специфичные параметры плагина.
    PARAM_SPEC: dict = {}

    #: Общие параметры семейства (переопределяется в SeriesBase и др.).
    BASE_PARAM_SPEC: dict = {}

    # ------------------------------------------------------------------
    # Инициализация
    # ------------------------------------------------------------------

    def __init__(self, params: dict[str, Any] | None = None):
        """
        Принимает:
            params — словарь параметров.
        """
        self.params = dict(params or {})

    # ------------------------------------------------------------------
    # Имена
    # ------------------------------------------------------------------

    @classmethod
    def get_display_name(cls) -> str:
        """Короткое имя: display_name или name."""
        return cls.display_name or cls.name

    # ------------------------------------------------------------------
    # PARAM_SPEC производные
    # ------------------------------------------------------------------

    @classmethod
    def param_spec(cls) -> dict:
        """
        Полная спецификация: BASE_PARAM_SPEC + PARAM_SPEC.

        Возвращает:
            свежий словарь (не мутируется).
        """
        spec = dict(cls.BASE_PARAM_SPEC)
        spec.update(cls.PARAM_SPEC)
        return spec

    @classmethod
    def default_params(cls) -> dict:
        """
        Значения по умолчанию (из spec["default"]).

        Возвращает:
            {param: default}.
        """
        return {k: s["default"]
                for k, s in cls.param_spec().items()
                if "default" in s}

    @classmethod
    def required_params(cls) -> set:
        """
        Обязательные параметры (из spec["required"]).

        Возвращает:
            множество имён.
        """
        return {k for k, s in cls.param_spec().items() if s.get("required")}

    # ------------------------------------------------------------------
    # Валидация
    # ------------------------------------------------------------------

    @classmethod
    def validate_params(cls, params: dict) -> list:
        """
        Проверяет params на корректность.

        Принимает:
            params — словарь параметров.

        Возвращает:
            список ошибок (пустой, если всё ок).
        """
        errors = []
        missing = cls.required_params() - set(params.keys())
        if missing:
            errors.append(
                f"{cls.name}: missing required params: {sorted(missing)}"
            )
        return errors

    # ------------------------------------------------------------------
    # Форматирование
    # ------------------------------------------------------------------

    @classmethod
    def format_short_params(cls, params: dict) -> str:
        """
        Короткое представление params для легенд.

        Принимает:
            params — словарь параметров.

        Возвращает:
            строку без внешних скобок ('p2,w5').
        """
        return _format_short(cls.param_spec() or {}, params or {})