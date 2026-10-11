# postprocess — фильтры результата

Каждый файл в этой папке — один фильтр. Регистрация через
`@register("postprocess", "name")`. Autodiscovery запускается при
`import arbacc.postprocess`.

## Как добавить новый фильтр

1. Создай `arbacc/postprocess/my_filter.py`.
2. Наследуйся от `PostprocessorBase`.
3. Определи `name`, `display_name`, `PARAM_SPEC`.
4. Реализуй `apply(estimates, ctx) -> PostResult`.
5. Готово.

### Шаблон

```python
"""Краткое описание фильтра."""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.postprocess import PostprocessorBase, PostResult
from arbacc.core.registry import register


@register("postprocess", "my_filter")
class MyFilter(PostprocessorBase):
    """Полное описание."""

    name = "my_filter"
    display_name = "mf"
    consumes = "iterations"

    PARAM_SPEC = {
        "window": {
            "type": "int",
            "min": 3,
            "required": True,
            "default": 5,
            "short": "w",
            "hint": "нечётное, ≥ 3",
        },
    }

    def apply(self, estimates: list[Any], ctx: Context) -> PostResult:
        """Применяет фильтр к траектории."""
        window = int(self.params["window"])
        # ... преобразование estimates
        result_values = list(estimates)
        return PostResult(
            name=self.name,
            params=dict(self.params),
            values=result_values,
            final=result_values[-1] if result_values else None,
            meta={"window": window},
        )
```

## Уже реализованные фильтры

| Файл | name | display_name | Что |
|---|---|---|---|
| `kolmogorov_zurbenko.py` | `kolmogorov_zurbenko` | `kz` | итеративное скользящее среднее |
| `savitzky_golay.py` | `savitzky_golay` | `sg` | локальная полиномиальная аппроксимация |
| `median.py` | `median` | `med` | скользящая медиана |

## Ключевые правила

### `consumes = "iterations"` — единственный источник

Постобработка получает **траекторию оценок акселератора** — список
`estimates` (в порядке итераций). Это **единственный** вход.

Если нужно больше данных (например, сами члены ряда) — это **не**
постобработка. Постобработки в нашей архитектуре работают только
по выходу акселератора.

### Не расширяй источник

В отличие от акселератора, постобработка **не может** запросить
дополнительные элементы. Она видит готовый список и преобразует
его. Это важно для скорости: акселератор считается один раз,
фильтров может быть много, и каждый из них работает по готовому
результату.

### Возвращай `PostResult`

Обязательные поля `PostResult`:

| Поле | Что |
|---|---|
| `name` | имя фильтра |
| `params` | параметры, с которыми применялся |
| `values` | преобразованная последовательность |
| `final` | финальное скалярное значение |
| `meta` | словарь с метаданными (окна, длины, degradation) |

Если `values` пуст — `final = None`. Если `estimates` короче
`window`, фильтр возвращает последовательность **как есть** (в
`meta` пометь `degenerate: True`).

## Краевые эффекты

Скользящее окно теряет `window − 1` элементов с краёв. Если
`len(estimates) < window`, фильтр не может работать. В этом
случае:

```python
if n < window:
    return PostResult(
        name=self.name,
        params=dict(self.params),
        values=list(estimates),
        final=estimates[-1] if estimates else None,
        meta={"input_len": n, "output_len": n, "degenerate": True},
    )
```

Это лучше, чем падать с ошибкой: короткая последовательность —
нормальная ситуация, если акселератор остановился рано.

## Валидация параметров

Фильтр сам проверяет свои параметры при `apply`. Например, KZ
требует **нечётное** окно:

```python
if window < 3 or window % 2 == 0:
    raise ValueError(f"KZ window must be odd and >= 3, got {window}")
```

Ошибка вылетает в момент применения, а не в момент создания
инстанса. Это удобно: `execute_post` ловит и записывает
в `errors.log`.

## Отладка

- **Фильтр не улучшил точность.** Это **нормально**. KZ, SG и
  median подавляют шум, но не ускоряют сходимость. Эффект
  появляется на **зашумлённых** данных. На чистых рядах они
  могут даже ухудшить результат.
- **Медленно на больших окнах.** SG использует `mp.matrix` —
  O(window³) на точку. Для окон > 30 предвычисли веса один раз.
- **Краевые эффекты съели всё.** Если `input_len - 2*half < 1`,
  результат пуст. Уменьши `window` или увеличь длину траектории.
- **Median сортирует через `cmp_to_key`.** Это медленнее нативных
  ключей, но работает для чисел backend'а (у них нет `<`).

## Арифметика — только через backend

```python
# Правильно:
b = ctx.backend
total = ctx.number(0)
for v in window:
    total = b.add(total, v, ctx.dps)
avg = b.div(total, ctx.number(window), ctx.dps)

# Неправильно:
avg = sum(window) / len(window)   # сломается на arb
```

## Стиль

- Docstring модуля: что за фильтр, для чего полезен.
- В `apply` — короткий комментарий про алгоритм.
- В `meta` — метрики: длины, окна, degradation.
- `PARAM_SPEC`: с `hint` и `short`.