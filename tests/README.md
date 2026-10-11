# tests — автотесты arbacc

Все тесты запускаются одной командой через pytest. Каждый файл
отвечает за свою часть фреймворка.

## Запуск

**Все тесты:**

    python -m pytest tests/ -v

**Быстрые (без медленных и backend-тестов):**

    python -m pytest tests/ -v -m "not slow and not backend"

**Только тесты backend'ов:**

    python -m pytest tests/ -v -m backend

**Конкретный файл:**

    python -m pytest tests/test_precision.py -v

**Один тест:**

    python -m pytest tests/test_precision.py::test_add_sub_mul_div -v

**Показать print() в тестах:**

    python -m pytest tests/ -v -s

**Параллельно (нужен pytest-xdist):**

    python -m pytest tests/ -v -n auto

## Статистика

На момент последнего запуска:

- **266+ тестов**
- **~3 секунды** на всё

Быстрота важна: тесты запускаются после каждого изменения.

## Структура

| Файл | Что проверяет |
|---|---|
| `test_smoke.py` | всё импортируется, реестр заполнен |
| `test_registry.py` | PARAM_SPEC, display_name, format_short_params |
| `test_precision.py` | арифметика, dps, digits_of, sign |
| `test_backends_matrix.py` | попарное согласие backend'ов |
| `test_backends_reference.py` | сравнение с независимыми константами |
| `test_series.py` | все ряды |
| `test_noise.py` | все шумы + детерминизм |
| `test_accelerators.py` | акселераторы + сходимость |
| `test_stopping.py` | критерии |
| `test_postprocess.py` | фильтры |
| `test_envelopes.py` | огибающие |
| `test_runner.py` | expand, scope, plan, execute, skip, id |
| `test_cli.py` | CLI end-to-end |

## Уровни тестов

### Smoke — самый быстрый

Проверяет, что:
- все пакеты плагинов импортируются,
- реестр заполнен хотя бы одним представителем каждой категории,
- каждый плагин можно создать с `default_params`.

Если smoke падает — остальное не имеет смысла.

### Registry — каждый плагин проверяется автоматически

Параметризовано **по каждому зарегистрированному плагину**:
- `test_has_name_and_display` — есть `name` и `display_name`,
- `test_param_spec_valid` — PARAM_SPEC корректно оформлен,
- `test_default_params_satisfy_required` — defaults покрывают
  required (иначе «Add» в GUI создаст невалидный инстанс),
- `test_format_short_params_smoke` — не падает на defaults.

**При добавлении нового плагина эти тесты подхватят его
автоматически** — ничего менять не нужно.

### Precision — backend'ы и точность

- Round-trip: `число → строка → число` сохраняет dps.
- Арифметика: `+`, `−`, `×`, `÷`, `pow`, `sign`, `digits_of`.
- `test_backends_agree_on_basics` — все backend'ы согласны
  на sin/cos/exp/log/zeta.

### Backend matrix — попарное согласие

Для каждой пары backend'ов проверяет 8 функций × 2 dps:
sin, cos, exp, log, sqrt, zeta(3), zeta(5), gamma(0.5).

Ожидаем согласие ≥ dps − 5.

### Backend reference — независимые источники

Три уровня проверки:
- **A.** Опубликованные константы (60+ знаков).
- **B.** Python `Decimal` (независимая арифметика).
- **C.** `math` (double).

Если все три источника согласны с backend'ом — backend
действительно правильный.

### Series / Noise / Accelerators / Stopping / Postprocess / Envelopes

Параметризовано по всем реализациям. Добавление нового плагина
в соответствующую папку автоматически расширяет тестовое
покрытие.

### Runner — оркестрация

- `expand_node` — 6 случаев развёртки,
- `matches` — точное и префиксное совпадение,
- `node_id` — детерминизм и формат,
- `build_plan` — минимальный, полный, пустой, с ошибками,
- `execute_accel` / `should_skip` — сохранение и скип.

### CLI — end-to-end

- `validate` на валидном / плохом конфиге,
- `plan` создаёт `plan.jsonl`,
- `run` создаёт `progress.json`,
- `--skip-existing` работает.

## Фикстуры

Общие — в `conftest.py`:

| Фикстура | Что |
|---|---|
| `ctx` | `Context(mpmath, dps=50)`, session-scope |
| `ctx_arb` | `Context(arb, dps=50)`, требует `python-flint`, skip иначе |
| `low_ctx` | `Context(mpmath, dps=20)` |
| `tmp_output` | временная папка output |
| `config_minimal` | минимальный валидный конфиг |
| `config_full` | конфиг с развёрткой dps × series × noise × accel |

Плюс словарь `KNOWN` с эталонными значениями:

```python
KNOWN = {
    "zeta2": "1.64493...",
    "zeta3": "1.20205...",
    "sin_06": "0.56464...",
    "cos_06": "0.82533...",
    "pi": "3.14159...",
    "e": "2.71828...",
}
```

## Маркеры

В `pytest.ini` объявлены:

| Маркер | Что |
|---|---|
| `slow` | медленные тесты (>1 сек) |
| `backend` | тесты, требующие arb/flint |

Использование:

```python
@pytest.mark.slow
def test_something_long():
    ...

@pytest.mark.backend
def test_with_arb(ctx_arb):
    ...
```

## Как добавить тест

### Новый плагин

Если ты добавил `arbacc/series/my_series.py`:

1. **Ничего не делай для registry-тестов** — они подхватят
   автоматически.
2. **Для специфичного поведения** — добавь параметризованный
   тест в `test_series.py`:

```python
@pytest.mark.parametrize("alpha", [1.0, 2.0, 5.0])
def test_my_series(alpha, ctx):
    Cls = get("series", "my_series")
    s = Cls(params={"alpha": alpha})
    stream = s.build_stream(ctx)
    b = ctx.backend
    # ... проверки
```

### Новая фикстура

Если фикстура нужна в нескольких файлах — в `conftest.py`.
Если в одном — прямо в файле.

### Медленный тест

Помечай `@pytest.mark.slow`, чтобы его можно было исключить
через `-m "not slow"`.

### Тест требует arb

Используй фикстуру `ctx_arb` — она сделает `pytest.skip`, если
backend недоступен. Или пометь `@pytest.mark.backend`.

## `legacy/`

Старые скрипты `check_stage*.py`, `check_backends*.py`
перенесены в `tests/legacy/`. Они **не запускаются** через
pytest. Оставлены для справки — если нужно посмотреть «полный
сценарий» одной командой.

Их можно запустить вручную:

    python tests/legacy/check_stage5.py

Но обычный путь — `python -m pytest tests/`.

## Отладка

- **`ImportError`** — скорее всего, файл с тестом импортирует
  что-то из `arbacc`, что сломано. Запусти `pytest tests/test_smoke.py`
  отдельно, там видно точную причину.
- **Тест backend'а падает с `16 знаков`** — константа в
  `test_backends_reference.py` содержит опечатку. Запусти
  `python generate_constants.py` и обнови `REFS`.
- **Медленный тест** — пометь `@pytest.mark.slow`.
- **Хочешь видеть print** — добавь `-s` к команде.
- **Тест падает в одном порядке, проходит в другом** — где-то
  общее состояние (например, реестр плагинов). Проверь, что
  тесты не зависят от порядка.

## Правила стиля

- Имя теста — `test_<что проверяем>`, читается как утверждение.
- Параметризация — везде, где больше одного случая.
- Assert — с осмысленным сообщением:
  ```python
  assert d >= dps - 3, f"{backend} на {name}: только {d} знаков"
  ```
- Не бойся много маленьких тестов — лучше 100 быстрых, чем
  5 медленных.