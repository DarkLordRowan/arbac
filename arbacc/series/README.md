# series — источники рядов

Каждый файл в этой папке — один ряд. Регистрация через
`@register("series", "name")`. Autodiscovery запускается при
`import arbacc.series`.

## Как добавить новый ряд

1. Создай `arbacc/series/my_series.py`.
2. Наследуйся от `SeriesBase`.
3. Определи `name`, `display_name`, `PARAM_SPEC`.
4. Реализуй `generate(n, ctx)`.
5. Опционально: реализуй `analytic_sum(ctx)` — если знаешь
   точную сумму.
6. Готово. Autodiscovery подхватит.

### Шаблон

```python
"""Краткое описание ряда."""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.series import SeriesBase


@register("series", "my_series")
class MySeries(SeriesBase):
    """Полное описание."""

    name = "my_series"
    display_name = "mys"

    PARAM_SPEC = {
        "alpha": {
            "type": "float",
            "required": True,
            "default": 1.0,
            "short": "a",
            "hint": "α > 0",
        },
    }

    def generate(self, n: int, ctx: Context) -> Any:
        """n-й член ряда (0-based)."""
        alpha = ctx.number(self.params["alpha"])
        # формула: a_n = ...
        return ctx.backend.pow(alpha, ctx.number(n), ctx.dps)

    def analytic_sum(self, ctx: Context) -> Any:
        """Точная сумма через backend (опционально)."""
        # Если не знаешь формулу — не переопределяй метод.
        return None
```

## Уже реализованные ряды

| Файл | name | display_name | Что |
|---|---|---|---|
| `zeta.py` | `zeta` | `zeta` | `ζ(s) = Σ 1/n^s` |
| `geometric.py` | `geometric` | `geom` | `Σ q^n = 1/(1-q)` |
| `cos_series.py` | `cos` | `cos` | `cos(x)` через ряд Тейлора |
| `sin_series.py` | `sin` | `sin` | `sin(x)` через ряд Тейлора |
| `from_file.py` | `from_file` | `file` | CSV или TXT |

## Общие параметры всех рядов

Добавляются автоматически через `SeriesBase.BASE_PARAM_SPEC`:

- **`exact_sum`** — явная точная сумма (перебивает `analytic_sum`);
- **`n_raw`** — сколько членов рисовать в сыром виде
  (по умолчанию 100). Используется в preview, когда акселератора ещё
  нет.

Специфичные параметры каждый ряд задаёт в `PARAM_SPEC`.

## Как работает `exact_sum`

Порядок приоритета:

1. Если в `params` задан `exact_sum` — используется он.
2. Иначе вызывается `analytic_sum(ctx)`.
3. Если оба пусты — метрика `digits_gained` не считается.

**Важно:** `analytic_sum` должен вычислять значение **не через
свой же ряд**, а через независимый источник:

- `zeta` — `backend.zeta(s)`;
- `cos` — `backend.cos(x)`;
- `sin` — `backend.sin(x)`;
- `geometric` — формула `1/(1-q)` через backend;
- `from_file` — **не переопределяет** `analytic_sum` (мы не знаем
  формулу). Пользователь задаёт `exact_sum` вручную, если хочет
  считать `digits_gained`.

## Формат файлов для from_file

**CSV** с колонкой чисел (заголовок опционален):

```
value
1.0000000000000000000000000000000000000000000000000
0.50000000000000000000000000000000000000000000000000
0.33333333333333333333333333333333333333333333333333
```

**TXT** — по одному числу в строке:

```
1.0
0.5
0.33333333333333333333333333333333333333333333333333
```

**Числа пиши как строки** — иначе float потеряет точность ещё
до того, как мы их прочитаем.

**Кодировка:** используй `utf-8-sig` (значение по умолчанию) —
он корректно читает и UTF-8 с BOM (Windows), и UTF-8 без BOM.

## Отладка

- **Ряд не найден.** Проверь `import arbacc.series` перед
  использованием. Autodiscovery запускается при импорте пакета.
- **Точность низкая (15 знаков вместо 50).** Скорее всего,
  `analytic_sum` возвращает `float` вместо `ctx.backend.cos(...)`.
  Проверь: `with mp.workdps(...)` вокруг вызова mpmath — или
  используй `ctx.backend.*` напрямую.
- **`from_file` не читается.** Проверь `encoding`. Для
  Windows-файлов из Excel — `utf-8-sig`.

## Стиль

- Docstring модуля: что за ряд.
- Docstring класса: формула.
- Docstring `generate`: `a_n = ...`.
- `PARAM_SPEC`: с `hint` и `short`.
- **Никаких `import mpmath`** — только через `ctx.backend`.