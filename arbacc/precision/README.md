# precision — адаптеры длинной арифметики

Здесь backend'ы: `mpmath` (работает всегда), `arb` (требует
`python-flint`, регистрируется лениво).

## Философия

Вся арифметика идёт через backend. Нигде в коде фреймворка
(кроме самого backend'а) не должно быть прямого `import mpmath`.
Это позволяет сменить движок одной строкой в конфиге:

```json
"precision": {"backend": "arb", "dps": 50}
```

## Контракт PrecisionBackend

Каждый backend реализует абстрактный интерфейс из `base.py`:

**Преобразования:**
- `number(value, dps)` — привести к числу backend'а;
- `to_str(value, dps)`, `from_str(s, dps)` — сериализация.

**Арифметика:**
- `add`, `sub`, `mul`, `div`, `pow`, `neg`, `abs_val`.

**Математические функции:**
- `factorial`, `sin`, `cos`, `exp`, `log`, `zeta`, `gamma`.

**Метрики:**
- `abs_diff(a, b, dps)` — `|a − b|`;
- `digits_of(value, reference, dps)` — сколько верных цифр;
- `sign(a, dps)` — `-1 | 0 | +1`.

## dps — всегда десятичные значащие

**Пользователь всегда пишет `dps=50` — это 50 десятичных значащих
цифр.** Не биты, не «сколько после запятой». Каждый backend сам
переводит dps в своё внутреннее представление:

- mpmath: работает в десятичных, конвертация не нужна.
- arb: `bits = ceil(dps * log2(10)) + 20`.

## Файлы

| Файл | Что |
|---|---|
| `base.py` | `PrecisionBackend(ABC)` + реестр + `register_backend` |
| `mpmath_backend.py` | реализация через mpmath |
| `arb_backend.py` | реализация через python-flint (arb) |
| `__init__.py` | autodiscovery всех `*_backend.py` |

## Autodiscovery

Любой файл вида `*_backend.py` в этой папке автоматически
импортируется при `import arbacc.precision`. Если импорт
не удался (например, `flint` не установлен) — файл тихо
пропускается, backend недоступен.

## Как добавить backend (третий)

Пример для `gmpy2`:

1. Установи: `pip install gmpy2`.

2. Создай `arbacc/precision/gmpy2_backend.py`:

```python
from __future__ import annotations
import math
from typing import Any

import gmpy2

from arbacc.precision.base import PrecisionBackend, register_backend


@register_backend("gmpy2")
class Gmpy2Backend(PrecisionBackend):
    name = "gmpy2"

    @staticmethod
    def _bits(dps: int) -> int:
        return int(math.ceil(dps * math.log2(10))) + 20

    def number(self, value: Any, dps: int) -> Any:
        gmpy2.get_context().precision = self._bits(dps)
        if isinstance(value, gmpy2.mpfr):
            return value
        return gmpy2.mpfr(str(value))

    # ... и так далее для всех абстрактных методов.
```

3. **Больше ничего.** Autodiscovery подхватит автоматически.
   В конфиге: `"backend": "gmpy2"`.

## Проверка backend'ов

В `tests/` есть три файла:

| Файл | Что проверяет |
|---|---|
| `test_precision.py` | арифметика, dps, метрики, `sign` |
| `test_backends_matrix.py` | попарное согласие backend'ов |
| `test_backends_reference.py` | сравнение с независимыми константами |

Запуск:

```powershell
python -m pytest tests/test_backends_reference.py -v
python -m pytest tests/test_backends_matrix.py -v
```

## Уроки точности (важно!)

**mpmath хранит фиксированное число ЗНАЧАЩИХ цифр.** Абсолютная
точность зависит от порядка числа:

| Число | dps | Абсолютных цифр |
|---|---|---|
| `10^-20` | 30 | 30 + 20 = **50** |
| `1` | 30 | 30 |
| `10^20` | 30 | 30 − 20 = **10** |

Это **не баг mpmath**, а физика чисел с относительной точностью.
Следствие: если работаешь с рядом, у которого предел `10^6`,
ставь `dps ≥ 40`, иначе `digits_gained` покажет меньше, чем
ты ожидаешь.

**arb честнее.** Он возвращает интервал `[значение ± погрешность]`.
Наш `arb_backend.to_str` извлекает центр, но погрешность можно
посмотреть напрямую:

```python
from flint import arb, ctx as flint_ctx
flint_ctx.prec = 200
print(arb("0.6").cos())   # [0.8253... +/- 1.69e-60]
```

Если `err` мал — знаем, сколько верных цифр у нас есть. У mpmath
такой информации нет: он просто «обещает» dps цифр и не сообщает
свою погрешность.

## Отладка

- **Backend не найден.** `list_backends()` покажет доступные имена.
  Если `arb` нет — `python-flint` не установлен или импорт упал
  с ошибкой.
- **Числа теряют точность.** Проверь `dps`. Помни про
  относительность: `10^20` при dps=30 даёт 10 абсолютных цифр.
- **`digits_of` даёт странное.** Формула — `floor(-log10(|a − b|))`.
  Если `a == b`, возвращает `dps`. Не используй `digits_of` для
  сравнения (`>` / `<`) — для этого есть `sign(a - b)`.

## Стиль

- Методы оборачивают тело в `with mp.workdps(dps):` (или эквивалент).
- **Никакой арифметики через `+`, `*`, `**` напрямую** — только
  через методы backend'а.
- Новый метод в `PrecisionBackend` — только если он нужен **хотя
  бы двум** реализациям. Частные — в конкретном backend'е.