# accelerators — алгоритмы ускорения сходимости

Каждый файл в этой папке — один акселератор. Регистрация через
`@register("accelerators", "name")`. Autodiscovery запускается при
`import arbacc.accelerators`.

## Как добавить новый акселератор

1. Создай `arbacc/accelerators/my_algo.py`.
2. Наследуйся от `AcceleratorBase`.
3. Определи `name`, `display_name`, `PARAM_SPEC`.
4. Реализуй `required_input(state)` и `step(source, state, ctx)`.
5. Готово.

### Шаблон

```python
"""Краткое описание алгоритма."""

from __future__ import annotations
from typing import Any

from arbacc.core.accelerator import AcceleratorBase, AlgoState
from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.stream import Stream


@register("accelerators", "my_algo")
class MyAlgo(AcceleratorBase):
    """Полное описание."""

    name = "my_algo"
    display_name = "mya"

    PARAM_SPEC = {
        "order": {
            "type": "int",
            "default": 3,
            "short": "o",
            "hint": "порядок таблицы",
        },
    }

    def required_input(self, state: AlgoState) -> int:
        """Сколько членов нужно на следующей итерации."""
        return state.iteration + 3

    def step(
        self,
        source: Stream,
        state: AlgoState,
        ctx: Context,
    ) -> AlgoState:
        """Одна итерация."""
        b = ctx.backend
        k = state.iteration
        # Возьми члены источника: source.get(0), source.get(1), ...
        # Раннер УЖЕ дотянул источник до required_input(state) - 1.
        partials = state.extra.get("partials", [])
        # ... вычисления
        estimate = partials[-1] if partials else ctx.number(0)
        new_state = state.with_estimate(estimate)
        new_state.extra["partials"] = partials
        return new_state
```

## Уже реализованные акселераторы

| Файл | name | display_name | Что |
|---|---|---|---|
| `aitken.py` | `aitken_delta2` | `aitd2` | Δ²-процесс Эйткена |
| `wynn_epsilon.py` | `wynn_epsilon` | `wynn` | ε-алгоритм Винна |

## Ключевые правила

### Акселератор — единственный узел, расширяющий источник

- `required_input(state)` возвращает **верхнюю границу** — сколько
  членов нужно на следующей итерации.
- Раннер сам решает, дотянуть ли источник (учитывая `n_max`).
- **`step` не должен вызывать `source.extend_to`** — это делает
  раннер **до** вызова `step`.

### Арифметика — только через backend

```python
# Правильно:
b = ctx.backend
x = b.add(a, c, ctx.dps)
y = b.pow(x, ctx.number(2), ctx.dps)

# Неправильно:
x = a + c                 # сломается на arb
y = x ** 2                # сломается на любом backend'е
```

### Состояние между итерациями — в `state.extra`

`AlgoState` — dataclass с полями `iteration`, `estimate`, `history`,
`extra`. Всё, что нужно для следующего шага (кэш частичных сумм,
ε-таблица), кладётся в `extra`:

```python
def step(self, source, state, ctx):
    partials = state.extra.get("partials", [])
    # ... используем partials
    new_state = state.with_estimate(new_estimate)
    new_state.extra["partials"] = partials
    return new_state
```

**Важно:** `with_estimate` копирует `extra` через `dict()`. Списки
внутри передаются по ссылке — это нормально, но осторожно при
мутации (мутируй только свою копию, если нужно).

### Возвращай НОВОЕ состояние

`step` должен возвращать `state.with_estimate(new_value)`,
а не мутировать `state.estimate` напрямую. Иначе `history` не
заполнится и критерии остановки не увидят данных.

## Как работает главный цикл

Из `arbacc/runner/run_accel.py`:

```python
while True:
    need = accelerator.required_input(state)
    if need > n_max:
        break
    source.extend_to(need - 1)     # дотягиваем источник
    state = accelerator.step(source, state, ctx)
    if stopping.should_stop(state, ctx):
        break
    for env in online_envelopes:
        env.push(state.estimate)
        if env.says_stop():
            break
```

То есть `step` вызывается **после** того, как источник уже
содержит нужное число членов. `source.get(n)` внутри `step`
не требует дополнительного дотягивания.

## Отладка

- **Не сходится.** Проверь `required_input`: возможно, растёт
  быстрее, чем `n_max`, и алгоритм не успевает.
- **`estimate` не обновляется.** Убедись, что `step` возвращает
  новое состояние через `with_estimate`.
- **`extra` теряется.** `with_estimate` копирует `extra` через
  `dict()`, но вложенные структуры — по ссылке.
- **Медленно на больших `n_max`.** Wynn ε пересчитывает всю
  таблицу на каждой итерации — O(k³) на итерацию. Инкрементальная
  версия — задача на будущее.

## Стиль

- Docstring модуля: формула, для чего полезен.
- В `step` — короткий комментарий, что происходит.
- Если `extra` — сложная структура, опиши её в docstring класса.
- `PARAM_SPEC`: с `hint` и `short`.
- Никаких `import mpmath` — только через `ctx.backend`.