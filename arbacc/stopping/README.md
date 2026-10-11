# stopping — критерии остановки

Каждый файл в этой папке — один критерий остановки. Регистрация
через `@register("stopping", "name")`. Autodiscovery запускается
при `import arbacc.stopping`.

## Как добавить новый критерий

1. Создай `arbacc/stopping/my_criterion.py`.
2. Наследуйся от `StoppingBase`.
3. Определи `name`, `display_name`, `PARAM_SPEC`.
4. Реализуй `should_stop(state, ctx)`.
5. Готово.

### Шаблон

```python
"""Краткое описание критерия."""

from __future__ import annotations

from arbacc.core.accelerator import AlgoState
from arbacc.core.context import Context
from arbacc.core.registry import register
from arbacc.core.stopping import StoppingBase


@register("stopping", "my_criterion")
class MyCriterion(StoppingBase):
    """Полное описание."""

    name = "my_criterion"
    display_name = "mc"

    PARAM_SPEC = {
        "n": {
            "type": "int",
            "min": 1,
            "required": True,
            "default": 100,
            "short": "n",
            "hint": "максимальное число итераций",
        },
    }

    def should_stop(self, state: AlgoState, ctx: Context) -> bool:
        """Проверяет, нужно ли остановиться."""
        limit = int(self.params["n"])
        if state.iteration >= limit:
            self._reason = f"my_criterion({limit})"
            return True
        return False
```

## Уже реализованные критерии

| Файл | name | display_name | Что |
|---|---|---|---|
| `max_iter.py` | `max_iter` | `maxi` | максимум N итераций |
| `digits_stable.py` | `digits_stable` | `dstab` | стабилизация цифр |
| `divergence.py` | `divergence` | `dvg` | расхождение |

## Ключевые правила

### Всегда выставляй `self._reason`

При `return True` **обязательно** выставить `self._reason` —
человекочитаемую строку. Она попадёт в `result.json` и покажет,
почему акселератор остановился:

```python
def should_stop(self, state, ctx):
    if condition:
        self._reason = f"my_criterion({param})"
        return True
    return False
```

Если забыть — `result.json` покажет пустой `stopped_by`,
и будет непонятно, что произошло.

### Никаких побочных эффектов, кроме `_reason`

Критерий **не должен** менять `state`, писать в файлы, печатать
в консоль. Только читает `state` и решает.

### Что видит критерий

Критерий не знает про акселератор. Он видит только `state`:

| Поле | Что |
|---|---|
| `state.iteration` | текущая итерация |
| `state.estimate` | текущая оценка предела |
| `state.history` | список всех предыдущих оценок |
| `state.extra` | специфичные поля конкретного акселератора |

Стандартные критерии работают с `iteration` и `history`. Если
нужен доступ к `extra` — это уже специализированный критерий.

### Сравнение чисел — через `sign`, не `digits_of`

```python
# Правильно: сравнить, что last > threshold
diff = b.sub(last, threshold, ctx.dps)
if b.sign(diff, ctx.dps) > 0:
    ...

# Неправильно: digits_of отвечает «насколько близки», не «больше/меньше»
d = b.digits_of(last, threshold, ctx.dps)
if d < 0:  # это не значит "больше"
    ...
```

## Как работают критерии в раннере

Из `arbacc/runner/run_accel.py`:

```python
if _should_stop(stopping_criteria, stopping_mode, state, ctx):
    break
```

Где `_should_stop` проверяет **все** критерии с учётом
`stopping_mode`:

- **`"any"`** — остановиться при **первом** сработавшем.
- **`"all"`** — только когда **все** сработали.

**Пример `any`:**

```json
"stopping": [
  {"type": "max_iter", "params": {"n": 1000}},
  {"type": "digits_stable", "params": {"window": 3, "min_digits": 20}}
],
"stopping_mode": "any"
```

Акселератор остановится, если **или** прошло 1000 итераций,
**или** цифры стабилизировались.

**Пример `all`:**

```json
"stopping": [
  {"type": "max_iter", "params": {"n": 100}},
  {"type": "divergence", "params": {"window": 5, "factor": "100"}}
],
"stopping_mode": "all"
```

Остановится, только если прошло 100 итераций **и** произошло
расхождение. Обычно не используется — `max_iter` как fallback
почти всегда идёт с `any`.

## Отладка

- **Срабатывает слишком рано.** Уменьши `min_digits` в
  `digits_stable` или увеличь `factor` в `divergence`.
- **Никогда не срабатывает.** Проверь `history` — если
  акселератор не заполняет её через `with_estimate`, критерий
  не увидит данных.
- **Ложное срабатывание `divergence`.** Фактор 100 подходит не
  всем рядам. Для колеблющихся последовательностей увеличь до 1000
  или больше.
- **`_reason` пуст.** Ты забыл выставить `self._reason` при
  возврате `True`.

## Стиль

- Docstring модуля: что проверяет критерий.
- Docstring `should_stop`: логика в одну фразу.
- Не забудь про `self._reason`.
- `PARAM_SPEC`: с `hint` и `short`.