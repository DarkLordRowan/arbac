# noise — модели шума

Каждый файл в этой папке — один шум. Регистрация через
`@register("noise", "name")`. Autodiscovery запускается при
`import arbacc.noise`.

## Как добавить новый шум

1. Создай `arbacc/noise/my_noise.py`.
2. Наследуйся от `NoiseBase`.
3. Определи `name`, `display_name`, `PARAM_SPEC`.
4. Реализуй `transform(n, value, ctx)`.
5. Готово.

### Шаблон (независимый шум)

```python
"""Краткое описание шума."""

from __future__ import annotations
from typing import Any

from arbacc.core.context import Context
from arbacc.core.noise import NoiseBase
from arbacc.core.registry import register
from arbacc.core.rng import CounterRNG


@register("noise", "my_noise")
class MyNoise(NoiseBase):
    """Полное описание."""

    name = "my_noise"
    display_name = "mn"
    access_mode = "random"

    PARAM_SPEC = {
        "sigma": {
            "type": "float",
            "required": True,
            "default": "1e-6",
            "short": "sig",
            "hint": "стандартное отклонение",
        },
    }

    def __init__(self, params=None, seed=0):
        super().__init__(params, seed)
        sigma = (params or {}).get("sigma", "0")
        # stream_id формируется из параметров: разные sigma дают
        # разные последовательности при одном seed.
        self._rng = CounterRNG(seed, f"my_noise|{sigma}")

    def transform(self, n: int, value: Any, ctx: Context) -> Any:
        """n-й зашумлённый элемент."""
        b = ctx.backend
        sigma = ctx.number(self.params["sigma"])
        z = ctx.number(self._rng.normal(n))
        delta = b.mul(sigma, z, ctx.dps)
        return b.add(value, delta, ctx.dps)
```

## Уже реализованные шумы

| Файл | name | display_name | Что |
|---|---|---|---|
| `none.py` | `none` | `none` | без шума |
| `gaussian.py` | `gaussian` | `gauss` | `N(0, σ)`, absolute/relative |
| `ar1.py` | `ar1` | `ar1` | `e_n = φ·e_{n-1} + σ·ε_n` |

## Ключевой принцип: детерминизм

**Значение шума для индекса n должно быть одинаковым независимо
от порядка запросов.** Это достигается через `CounterRNG`:

```python
from arbacc.core.rng import CounterRNG
rng = CounterRNG(seed=42, stream_id="gaussian|1e-6|abs")
z = rng.normal(n)   # чистая функция от (seed, n, params)
```

**Почему это важно:**

- Акселератор может запросить `source.extend_to(100)` — и `_NoisyStream`
  дотягивает 100 зашумлённых значений.
- Потом может запросить ещё 50 — и **первые 100 должны остаться
  теми же**. Обычный ГПСЧ (`random.Random`) этого не даёт: он
  хранит внутреннее состояние и зависит от порядка вызовов.
- `CounterRNG` решает эту проблему: значение = `hash(seed, n)`.

**Правило:** для независимых шумов всегда используй `CounterRNG`
с `stream_id`, включающим параметры шума.

## Forward-only шумы

Если шум имеет память (AR(1), ARMA), `access_mode = "forward_only"`:

- Запросы должны идти **по возрастанию n**.
- Запрос `n < last_n` → `RuntimeError`.
- `wrap` защищён от повторного вызова: один инстанс = один стрим.

Пример:

```python
class AR1Noise(NoiseBase):
    access_mode = "forward_only"

    def __init__(self, params=None, seed=0):
        super().__init__(params, seed)
        self._state = []
        self._last_n = -1
        self._wrapped = False

    def wrap(self, source, ctx):
        if self._wrapped:
            raise RuntimeError("AR1Noise.wrap already called")
        self._wrapped = True
        return super().wrap(source, ctx)

    def transform(self, n, value, ctx):
        if n < self._last_n:
            raise RuntimeError(f"forward-only: n={n}, last={self._last_n}")
        # ... досоздание состояния
```

## Режимы `mode` для гауссова шума

- `mode="absolute"` — добавляем `σ · N(0,1)`.
- `mode="relative"` — добавляем `σ · |value| · N(0,1)`.

Для значений, близких к нулю, `relative`-шум стремится к нулю.
Это может быть неожиданно — учитывай.

## Отладка

- **Шум сломал детерминизм.** Проверь, что используешь `CounterRNG`,
  а не `random.Random`. Обычный ГПСЧ хранит состояние.
- **AR(1) бросает `RuntimeError`.** Ты запросил `n < last_n`.
  Порядок вызовов должен быть возрастающим.
- **Повторный `wrap` падает.** Это правильно для forward-only.
  Создай новый инстанс шума для нового стрима.
- **Разные инстансы шума коррелируют.** Убедись, что `stream_id`
  в `CounterRNG` включает параметры (sigma, mode, phi).

## Стиль

- Docstring модуля: модель шума, формула.
- Docstring `transform`: что происходит (`value + noise`).
- Для forward-only — переопределяй `wrap` с защитой от повтора.
- `PARAM_SPEC`: с `hint` и `short`.
- Арифметика — только через `ctx.backend.*`.