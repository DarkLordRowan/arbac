# core — ядро фреймворка

Здесь контракты и общие механизмы. Ядро **не знает** про конкретные
плагины (zeta, wynn, kz). Оно знает только абстракции: `Stream`,
`SeriesBase`, `NoiseBase`, `AcceleratorBase`, `StoppingBase`,
`PostprocessorBase`, `EnvelopeBase`.

## Ключевая идея: PluginBase

Все плагины — потомки `PluginBase`. Он даёт:

| Метод | Что делает |
|---|---|
| `get_display_name()` | короткое имя для легенд |
| `param_spec()` | BASE_PARAM_SPEC + PARAM_SPEC |
| `default_params()` | `{param: default}` |
| `required_params()` | `{param, ...}` |
| `validate_params(params)` | список ошибок |
| `format_short_params(params)` | `'p2,w5'` для легенд |

Конкретный плагин объявляет **только**:

```python
class MyAlgo(AcceleratorBase):
    name = "my_algo"            # стабильный id (в путях)
    display_name = "mya"        # для легенд
    PARAM_SPEC = {              # единственный источник правды
        "order": {"type": "int", "default": 3, "short": "o"},
    }
    def required_input(self, state): ...
    def step(self, source, state, ctx): ...
```

Ничего больше — ни `__init__`, ни `default_params`, ни
`validate_params`. Всё в базе.

## Формат PARAM_SPEC

```python
PARAM_SPEC = {
    "имя": {
        # --- тип ---
        "type": "int" | "float" | "str" | "enum" | "file",

        # --- ограничения ---
        "min": ..., "max": ...,         # для чисел
        "values": [...],                # для enum

        # --- семантика ---
        "required": True,               # обязательный
        "default": ...,                 # значение по умолчанию
        "hint": "...",                  # подсказка в GUI

        # --- отображение ---
        "short": "p",                   # короткое имя в легендах
        "short_values": {...},          # короткие значения enum
        "hidden": True,                 # скрыть из легенды
    },
}
```

## Файлы

| Файл | Что |
|---|---|
| `plugin.py` | `PluginBase` — общий предок плагинов |
| `_short.py` | форматирование params для легенд |
| `context.py` | `Context` — backend + dps, проносится через всю цепочку |
| `stream.py` | `Stream` — Protocol продуцируемой последовательности |
| `series.py` | `SeriesBase` + `_SeriesStream` |
| `noise.py` | `NoiseBase` + `_NoisyStream` |
| `accelerator.py` | `AcceleratorBase` + `AlgoState` |
| `stopping.py` | `StoppingBase` |
| `envelope.py` | `EnvelopeBase` |
| `postprocess.py` | `PostprocessorBase` + `PostResult` |
| `result.py` | `AcceleratedResult`, `IterationRecord` |
| `registry.py` | реестр плагинов + валидация PARAM_SPEC |
| `rng.py` | `CounterRNG` — детерминированный ГПСЧ |

## Как расширять

**Новый базовый тип плагина** (например, `preprocess`):

1. Создай `core/my_thing.py` с `MyThingBase(PluginBase)`.
2. Зарегистрируй autodiscovery в `arbacc/runner/__init__.py`.
3. Создай папку `arbacc/my_things/` с плагинами.

**Новое поле в PARAM_SPEC** (например, `"unit": "Hz"`):

1. Добавь обработку в `_short.py` или `plugin.py`.
2. Обнови README выше.
3. Старые плагины не пострадают.

**Новый backend** — см. `../precision/README.md`.

## Как работает Context

`Context` — immutable-объект с двумя полями:

- `backend` — экземпляр `PrecisionBackend` (mpmath, arb, ...).
- `dps` — число десятичных значащих цифр.

Все вычисления идут **через backend**:

```python
x = ctx.number("0.6")               # привести к числу backend'а
y = ctx.backend.cos(x, ctx.dps)     # cos в нужной точности
```

**Никогда** не используй `+`, `*`, `**` напрямую — только методы
`ctx.backend.*`. Это позволяет сменить mpmath на arb без правки кода.

## Отладка

- **Плагин не найден.** Проверь `import arbacc.<kind>` в
  `arbacc/runner/__init__.py` — autodiscovery запускается при импорте.
- **PARAM_SPEC ошибка при регистрации.** `register()` бросает
  `ValueError` с описанием — читай текст.
- **`format_short_params` странно.** Смотри `short` в PARAM_SPEC.
- **Кэш `skip_existing` сломался.** Проверь, что `name` плагина
  не менялся — он входит в `input_hash`.

## Правила стиля

- Docstring обязателен у класса и публичных методов.
- `PARAM_SPEC` — константа класса.
- Общее — в `PluginBase`, семейное — в `BASE_PARAM_SPEC`.
- **Никогда не давай локальной переменной имя импортированной
  функции:** `alabel = accel_label(...)`, а не
  `accel_label = accel_label(...)`.