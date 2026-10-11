# runner — планировщик и исполнитель

Оркестрация: развёртка параметров, построение плана, выполнение
задач, скип, прогресс, ошибки.

## Файлы

| Файл | Что |
|---|---|
| `expand.py` | `expand_node`, `expand_all` — развёртка массивов |
| `scope.py` | `matches(applies_to, context)` — область действия |
| `id.py` | `node_id`, `canonical_json` — единый id |
| `plan.py` | `build_plan(config)` — двухуровневый план |
| `execute.py` | `execute_accel`, `execute_post` — прогон одной задачи |
| `skip.py` | `should_skip`, `expected_manifest`, `build_input_payload` |
| `progress.py` | `Progress` — `progress.json` |
| `errors.py` | `ErrorLog` — `errors.log` |
| `run_accel.py` | `run_accelerator` — главный цикл акселератора |
| `run_postprocess.py` | `run_offline_envelopes`, `run_postprocessors` |
| `save_result.py` | `save_accelerated_result` |
| `metrics.py` | `digits_gained`, `envelope_was_right` |

## План — двухуровневый

`build_plan(config)` возвращает словарь:

```python
{
    "accel": [...],   # задачи акселерации
    "post":  [...],   # задачи постобработки
    "errors": [...],  # ошибки валидации
}
```

**Почему два уровня.** Акселератор — самая дорогая часть. Он
считается **один раз** на тройку (series, noise, accelerator) с
учётом dps. Постобработок может быть много, каждая читает
**готовый результат** из accel-задачи. Это экономит часы на
больших прогонах.

## Как работает `plan.py`

Пять шагов:

1. **Развёртка.** `expand_all(config["series"])` и т.д. разворачивают
   массивы параметров в декартово произведение.
   `{"x": [0.6, 1]}` → две серии.
2. **Нормализация.** `exact_sum` из верхнего уровня серии переносится
   в `params`, чтобы не потеряться при `_strip`.
3. **Валидация.** Каждый узел проверяется через
   `Cls.validate_params(params)`. Ошибки собираются в `errors`.
4. **Scope.** Для каждой комбинации проверяется `applies_to` через
   `matches`. Поддерживается префиксное совпадение:
   `"zeta"` матчит `"zeta_s3"`.
5. **id.** Вычисляется через `node_id(kind, type, params, extra)`.
   **Никогда не берётся из JSON.** Это позволяет одной карточке
   с `x=[0.6, 1]` дать две задачи с разными id.

## Как работает `execute.py`

**`execute_accel(task, output_root)`:**

1. Строит `Context(backend, dps)`.
2. Создаёт `SeriesCls(params, exact_sum)`, `NoiseCls(params, seed)`.
3. Оборачивает: `noisy = noise.wrap(source, ctx)`.
4. Создаёт `AcceleratorCls(params)`.
5. Прогоняет `run_accelerator(...)` с критериями из `task["stopping"]`.
6. Сохраняет результат через `save_accelerated_result`.

**`execute_post(task, output_root)`:**

1. Читает `result.json` и `iterations.jsonl` родителя.
2. Если родитель `failed` — возвращает `status="skipped"`.
3. Восстанавливает `AcceleratedResult` из сохранённых данных.
4. Применяет postprocessors и envelopes (`run_mode="after"`).
5. Сохраняет через `save_postprocess_results`.

## Как работает `run_accelerator`

Главный цикл:

```python
while True:
    need = accel.required_input(state)
    if need > n_max:
        break
    source.extend_to(need - 1)
    state = accel.step(source, state, ctx)
    if stopping.should_stop(state, ctx):
        break
    for env in online_envelopes:
        env.push(state.estimate)
        if env.says_stop():
            break
```

**Важно:** `extend_to` идемпотентен — повторный вызов с тем же
`n` ничего не делает. Акселератор свободно запрашивает больше
членов, не заботясь о том, что уже запрошено.

## `skip_existing`

Через `input_hash`. **Payload для хеша — одна функция**
`build_input_payload(task)` в `skip.py`. Она используется и при
сохранении (`execute.py`), и при проверке (`should_skip`).

Если бы payload строился в двух местах, они бы разошлись, и
skip сломался бы. **Правило: один источник правды.**

`expected_manifest(task) = build_manifest(build_input_payload(task))`.

## `id.py` — единый id

Формат:

```
<type>_<short1><val1><short2><val2>...
```

Примеры:

| Узел | id |
|---|---|
| `series/zeta {"s": 3}` | `zeta_s3` |
| `series/cos {"x": 0.6}` | `cos_x0p6` |
| `noise/gaussian {"sigma": "1e-6"} seed=42` | `gaussian_sig1em6_seed42` |
| `accelerators/aitken_delta2 {}` dps=50 | `aitken_delta2_dps50` |
| `envelopes/emd {..., "run_mode": "after"}` | `emd_w15dw11th0p5mh20rmafuaobs` |

Порядок параметров — **как в PARAM_SPEC** плагина. Автор плагина
ставит главные параметры первыми.

Один id для всего: в путях output, в `task_id`, в `applies_to`.

## `expand.py` — правила развёртки

| Значение | Разворачивается? |
|---|---|
| `{"a": 1}` | нет, один вариант |
| `{"a": [1, 2, 3]}` | да, 3 варианта |
| `{"a": [1, 2], "b": [3, 4, 5]}` | да, 6 вариантов |
| `{"a": {"x": [1, 2]}}` | да, 2 варианта (рекурсивно) |
| `{"applies_to": ["x", "y"]}` | **нет**, это предикат |
| `{"stopping": [{...}, {...}]}` | **нет**, это массив критериев |

**Исключение:** поля из `_NON_EXPANDABLE` (`applies_to`,
`stopping`) не разворачиваются. Это семантически предикаты или
массивы под-узлов, а не параметры.

## Отладка

- **`build_plan` падает.** Проверь обязательные секции
  (`precision`, `series`, `accelerators`). Ошибки — в `errors`.
- **`should_skip` = False на посчитанном.** Сравни `input_hash` в
  `manifest.json` и `build_input_payload(task)`. Должны совпадать.
- **`execute_post` `FileNotFoundError`.** Родительский accel
  не посчитан или упал. Проверь `out/accel/.../result.json`.
- **Двухуровневый план работает не так.** `plan["accel"]` для
  акселерации, `plan["post"]` для постобработки. Post-задачи
  читают результат родителя через `parent_task_id`.
- **`applies_to` не срабатывает.** Проверь, что id читаемый
  (`zeta_s3`), а не хэш. Префиксное совпадение работает через
  разделитель `_`.

## Стиль

- Публичные функции — с docstring.
- `execute_*` возвращают `{"status", "task_id", ...}`. Не бросают
  исключения — ловят и возвращают `failed`.
- Логирование — через `ErrorLog`, не через `print`.
- **Единственный источник правды** для id — `id.py`, для payload
  для хеша — `build_input_payload`.