# envelopes — скользящие огибающие

Каждый файл в этой папке — одна огибающая. Регистрация через
`@register("envelopes", "name")`. Autodiscovery запускается при
`import arbacc.envelopes`.

## Как добавить новую огибающую

1. Создай `arbacc/envelopes/my_env.py`.
2. Наследуйся от `EnvelopeBase`.
3. Определи `name`, `display_name`, `PARAM_SPEC`.
4. Реализуй `push(value)`, `says_stop()`, `result()`.
5. Готово.

### Шаблон

```python
"""Краткое описание огибающей."""

from __future__ import annotations
from typing import Any

from arbacc.core.envelope import EnvelopeBase
from arbacc.core.registry import register


@register("envelopes", "my_env")
class MyEnv(EnvelopeBase):
    """Полное описание."""

    name = "my_env"
    display_name = "me"

    PARAM_SPEC = {
        "window": {
            "type": "int",
            "min": 3,
            "required": True,
            "default": 11,
            "short": "w",
            "hint": "длина окна",
        },
        "threshold": {
            "type": "float",
            "min": 0,
            "max": 1,
            "default": 0.5,
            "short": "th",
            "hint": "доля от пика амплитуды",
        },
        "run_mode": {
            "type": "enum",
            "values": ["during", "after"],
            "default": "after",
            "short": "rm",
            "short_values": {"during": "du", "after": "af"},
        },
        "used_as": {
            "type": "enum",
            "values": ["observer", "stopping_criterion"],
            "default": "observer",
            "short": "ua",
            "short_values": {
                "observer": "obs",
                "stopping_criterion": "sc",
            },
        },
    }

    def __init__(self, params=None):
        super().__init__(params)
        params = params or {}
        self._window = int(params.get("window", 11))
        self._threshold = float(params.get("threshold", 0.5))
        if "run_mode" in params:
            self.run_mode = params["run_mode"]
        if "used_as" in params:
            self.used_as = params["used_as"]

        self._values: list[float] = []
        self._stop_at: int | None = None

    def push(self, value: Any) -> None:
        """Добавляет очередное значение траектории."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = 0.0
        self._values.append(v)
        # ... анализ

    def says_stop(self) -> bool:
        """True, если пора остановиться."""
        return (
            self._stop_at is not None
            and self.used_as == "stopping_criterion"
        )

    def result(self) -> dict[str, Any]:
        """Итоговые метаданные."""
        return {
            "envelope": self.name,
            "suggested_stop_at": self._stop_at,
            "n_values": len(self._values),
            "window": self._window,
            "threshold": self._threshold,
        }
```

## Уже реализованные огибающие

| Файл | name | display_name | Что |
|---|---|---|---|
| `hilbert_sliding.py` | `hilbert` | `hilb` | FIR-Гильберт, амплитуда колебаний |
| `emd_sliding.py` | `emd` | `emd` | упрощённый EMD |

## Два режима: `run_mode`

- **`"during"`** — огибающая подключается к циклу акселератора.
  На каждой итерации вызывается `push(state.estimate)`, и если
  `says_stop()` вернёт `True` — акселератор останавливается.
- **`"after"`** — огибающая работает **после** акселератора по
  сохранённой траектории. Не может остановить, только наблюдает.

## Две роли: `used_as`

- **`"stopping_criterion"`** — огибающая **решает** остановку.
  Работает только с `run_mode="during"`.
- **`"observer"`** — только **отмечает** точку, где следовало
  остановиться. Результат сохраняется в `comparison`, чтобы потом
  сравнить с фактической остановкой (`envelope_was_right`).

**Типичная комбинация:**

| `run_mode` | `used_as` | Смысл |
|---|---|---|
| `during` | `stopping_criterion` | реально останавливает |
| `after` | `observer` | только предлагает точку |

## Ключевое: работа с трендом

**Огибающая работает не с самими оценками, а с их отклонениями
от локального тренда.** Иначе сигнал стремится к пределу, и
огибающая тоже — порог никогда не срабатывает.

В `HilbertSliding` и `EMDSliding` это делается через
`detrend_window`:

```python
def _detrend(self, values):
    w = self._detrend_window
    out = []
    for i, v in enumerate(values):
        lo = max(0, i - w + 1)
        window_vals = values[lo:i + 1]
        m = sum(window_vals) / len(window_vals)
        out.append(v - m)
    return out
```

Остаток содержит только колебания. Амплитуда остатка —
огибающая.

## Обязательные поля `result`

GUI и метрики ожидают в `result()`:

| Поле | Что |
|---|---|
| `envelope` | имя огибающей |
| `suggested_stop_at` | индекс k, где предлагается остановка (или None) |
| `window` | параметр |
| `threshold` | параметр |
| `envelope_values` | список амплитуд (для визуализации) |
| `envelope_indices` | список k (индексов) |
| `envelope_upper` | `signal + amplitude` |
| `envelope_lower` | `signal - amplitude` |

Без `envelope_values`, `envelope_upper`, `envelope_lower` GUI
не сможет нарисовать огибающую. `envelope_indices` нужны для
правильного позиционирования на графике: амплитуда появляется
начиная с итерации `window-1`, а не с 0.

## Отладка

- **`suggested_stop_at = None`.** Порог не достигнут. Увеличь
  `threshold` (например, 0.9) или уменьши `min_history`.
- **`envelope_was_right = False`.** Это **не ошибка**. Огибающая
  предложила остановиться раньше, чем акселератор достиг лучшей
  точности. Важная метрика для калибровки порогов.
- **`detrend_window` слишком мал.** Тренд удаляется плохо,
  амплитуда не падает. Ставь `detrend_window ≥ window`.
- **Амплитуды все нули.** Проверь, что огибающая работает с
  **остатком**, а не с исходным сигналом.

## Стиль

- Docstring модуля: что за огибающая, зачем.
- В `push` — короткий комментарий про вычисление амплитуды.
- В `result` — все метрики для анализа.
- `PARAM_SPEC`: с `hint`, `short`, `short_values` для enum.