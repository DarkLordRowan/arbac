# storage — сохранение и загрузка

Всё, что касается записи на диск и чтения.

## Файлы

| Файл | Что |
|---|---|
| `manifest.py` | `build_manifest`, `input_hash`, `code_version`, `deps_versions` |
| `jsonl.py` | `write_jsonl`, `read_jsonl`, `stream_to_jsonl` |
| `save.py` | `save_series`, `save_noise` |

## Форматы

### Stream — JSONL

Одна строка = один элемент.

```json
{"n": 0, "value": "1.0000000000000000000000000000000000000000000000000"}
{"n": 1, "value": "0.12500000000000000000000000000000000000000000000000"}
```

Числа — **строки**, не float. Иначе потеряется точность. При
записи используется `backend.to_str(value, dps)`, при чтении —
`backend.from_str(s, dps)`.

### Manifest — JSON

Метаданные инстанса.

```json
{
    "input_hash": "sha256:9f8e7d6c...",
    "code_version": "git:abc123",
    "deps": {"python": "3.13.0", "mpmath": "1.4.1"},
    "created_at": "2026-09-13T12:34:56Z",
    "input": {...}
}
```

### Output — структура

```
out/{run_id}/
  plan.jsonl                       список всех задач
  progress.json                    прогресс выполнения
  errors.log                       лог ошибок
  accel/{series_id}/{noise_id}/{accel_id}/
    manifest.json                  метаданные для skip_existing
    iterations.jsonl               траектория итераций
    result.json                    финальный результат
  postprocess/{series_id}/{noise_id}/{accel_id}/
    manifest.json
    filters/{filter_name}/
      values.jsonl                 последовательность после фильтра
      summary.json                 метрики фильтра
    envelopes/{envelope_name}/
      summary.json                 метаданные огибающей
```

### Пример `result.json`

```json
{
    "accelerator": "aitken_delta2",
    "params": {},
    "estimate": "1.202056903159594285399738161511449990764986292...",
    "n_used": 87,
    "n_max": 1000,
    "stopped_by": "digits_stable(window=3, min_digits=50)",
    "status": "ok",
    "error": null,
    "digits_gained": 74,
    "meta": {}
}
```

### Пример `iterations.jsonl`

```json
{"k": 0, "estimate": "1.20205...", "n_used": 3}
{"k": 1, "estimate": "1.202056...", "n_used": 5}
```

## Ключевые принципы

### Числа — всегда строки

Через `backend.to_str` и `backend.from_str`. **Никогда**
`str(float)`. Float теряет точность уже при записи; при чтении
восстановить нельзя.

### Запись атомарная

Все записи — через tmp + rename. См. `_write_manifest`:

```python
tmp = path.with_suffix(".tmp")
with tmp.open("w", encoding="utf-8") as f:
    json.dump(manifest, f, ...)
tmp.replace(path)
```

Если процесс упадёт в момент записи — старый файл останется
целым.

### `input_hash` — единый источник

Payload для хеша строится **одной функцией**
`build_input_payload(task)` в `runner/skip.py`. Она используется
и при сохранении, и при проверке `should_skip`.

Если бы payload строился в двух местах, рано или поздно они
разошлись бы, и `skip_existing` сломался бы.

## Как расширять

### Новый формат stream (например, gzip)

Модифицируй `write_jsonl` и `read_jsonl`. Добавь параметр
`compress=False`. При `compress=True` оборачивай в
`gzip.open(path, "wt", encoding="utf-8")`.

### Parquet для больших данных

Отдельный модуль. Числа — строками (иначе теряется точность).
Используй `pyarrow`:

```python
import pyarrow as pa
import pyarrow.parquet as pq

table = pa.table({"n": ns, "value": values_str})
pq.write_table(table, path)
```

### Сводный CSV с метриками

Отдельный модуль в `reporting/`. Читает все `result.json` и
складывает в одну таблицу:

| task_id | digits_gained | n_used | stopped_by |
|---|---|---|---|
| `zeta_s3__none__aitken_delta2_dps30` | 74 | 87 | `digits_stable` |
| `zeta_s3__gauss_sig1em6_seed42__wynn_dps50` | 45 | 30 | `max_iter` |

## Как читать output

Из Python:

```python
from pathlib import Path
from arbacc.storage.jsonl import read_jsonl
import json

accel_dir = Path("out/exp_001/accel/zeta_s3/none/aitken_delta2_dps30")

# Результат
result = json.loads((accel_dir / "result.json").read_text("utf-8"))
print(result["estimate"], result["stopped_by"])

# Траектория
for rec in read_jsonl(accel_dir / "iterations.jsonl"):
    print(rec["k"], rec["estimate"][:30], rec["n_used"])
```

## Отладка

- **`input_hash` не совпадает.** Payload строится в одном месте
  (`build_input_payload`). Если дублировать — разойдётся.
- **Числа теряют точность при чтении.** Проверь, что в JSONL
  они строками. Если float — потеря случилась при записи.
- **BOM в файлах.** Для CSV/TXT используй `encoding="utf-8-sig"`.
  Для JSON-конфигов — тоже.
- **Странные пути в output.** `series_id`, `noise_id`, `accel_id` —
  это `node_id` из `runner/id.py` (читаемые). Если в путях хэши
  (`zeta__cc44bbee`) — старая версия фреймворка.

## Стиль

- Все записи — атомарные (tmp + rename).
- Числа — только через backend.
- Манифест обязателен для каждого инстанса.
- Одна функция для payload `input_hash` — `build_input_payload`.