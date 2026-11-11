# Arbac Research v2 — расширенная аналитика готовых Parquet

Обновление **только исследовательского модуля** из v1, протестированного на Windows.
Запись JSON → ZSTD Parquet и восстановление готовых частей остаются прежними.
Ни `arbacc`, ни ветка GitHub `Magister` не изменяются.

## Установка в твоей схеме каталогов

```text
Desktop/
  Arbacv2/            <- распаковать v2 С ЗАМЕНОЙ файлов v1
    arbac_research/
    research_tests/
    RUN_RESEARCH_FULL.ps1
  arbac-Magister/     <- исходная библиотека, НЕ заменять
    arbacc/
```

Открой PowerShell в `Arbacv2`:

```powershell
python -m pip install -r requirements-research.txt
python -m pytest research_tests -q
python -m arbac_research gui .\out\research_smoke
```

GUI откроет **уже посчитанный** `research_smoke` из первого опыта. Прогон заново НЕ нужен.
Прежний `summary.parquet` пересчитывается автоматически из `trace/*.parquet`, потому
что версия формул/набор полей изменились; дорогие алгоритмы НЕ запускаются.

Теперь во вкладке `Анализ готового Parquet` есть четыре подвкладки:

1. `Обзор`: компактная таблица + задачи, выбор одной задачи для просмотра.
2. `Все групповые метрики`: выпадающее меню `Точность / Достижение ε /
   Робастность / Скорость / Все показатели`. Таблица горизонтально прокручивается.
3. `Паспорт выбранной задачи`: все доступные метрики и объяснения. Двойной щелчок
   по задаче в обзоре открывает паспорт.
4. `Определения и ограничения`: справочник с различием формул из C++ и тезиса.

CSV со всеми метриками:

```powershell
python -m arbac_research analyze .\out\research_smoke `
  --task-csv .\out\research_smoke\tasks_v2.csv `
  --group-csv .\out\research_smoke\groups_v2.csv
```

Более широкий вывод сразу в консоль (большой набор колонок):

```powershell
python -m arbac_research analyze .\out\research_smoke --detailed
```

Для *нового* полного эксперимента (без лимита задач):

```powershell
.\RUN_RESEARCH_FULL.ps1 `
  -Config .\examples\research_smoke.json `
  -Output .\out\research_next `
  -Workers 8 `
  -ArbacRoot "C:\Users\DLR_ACER\Desktop\arbac-Magister" `
  -RunTests
```

`-ArbacRoot` необязателен: скрипт автоматически ищет `arbac-Magister` рядом с
`Arbacv2`. Если ты уже установил `PYTHONPATH`, это тоже продолжит работать.
**Не используй smoke JSON для большой научной выборки:** он содержит только
одну задачу. Для полных исследований понадобится отдельный JSON.

## Что теперь считается по каждому заданию

**Точность и выигрыш.** `best_error`, `last_error`, `base_min_error`,
`base_last_error`, `base_error_at_best_n`, `base_error_at_last_n`,
`relative_error_best`, `gain_best_orders` (наш G_j), `gain_last_orders`,
`last_best_loss_orders`, `step_gain_{mean,median,min,max}_orders` и доля
шагов, где ускоритель лучше исходной последовательности.

**C++-метрики отдельными полями.** `cpp_orders_gain_vs_series_min`,
`cpp_relative_error_vs_series_min`, `cpp_amp_at_best_n_orders`,
`cpp_step_series_amp_{mean,median,worst}_orders`. Во всех `cpp_*` с точно
нулевой ошибкой сохранена специальная договорённость оригинального
`AlgoRankingTable.model.ts`: это **не** та же формула, что математический G_j.
В остальных случаях `cpp_orders_gain_vs_series_min` сравнивает независимо
лучшие ошибки двух траекторий, а `gain_best_orders` — ошибки при равном
числе входных членов. `cpp_step_series_amp` измеряет разность приближений
`|A_m-S_m|`, а не истинную ошибку `|A_m-S|`.

**Порог и скорость.** `base_first_epsilon_n`, `accel_first_epsilon_n`,
`epsilon_saved_terms` (если обе траектории достигли ε),
`successful_acceleration`, `epsilon_earlier`, `base_reached_epsilon`,
`accel_reached_epsilon`, `best_n`, `last_n`, `best_k`, `last_k`,
`elapsed_ms`, число корректных шагов.

**Робастность.** `status`, `failure_category`, `division_zero_failure`,
`n_points_invalid`, `sign_changes`, `one_sided`, `error_monotonicity`,
`error_increases`, `error_decreases`, `error_equals`,
`error_increase_share`, число сравнимых шагов.

**Группы.** C1/C5, доли от сравнимых случаев, покрытие ε, случаи с отказами,
медианы/средние/минимумы/максимумы выигрыша, P5/P95 выигрыша, лучший и
последний шаг, потеря точности, время и показатели устойчивости.
Все ранги и искусственный совокупный балл отсутствуют.

## Чего пока нет и почему

Сами колонки `op_add`, `op_mul`, `op_div`, `op_special`, `filter_trigger_n`,
`division_zero_first_n`, `division_zero_recovered` показываются в паспорте
задачи как **NULL**, потому что старый формат `trace v1` не содержит
профилировочных событий по шагам. Их нельзя восстановить по одним числам
приближения. Для них нужен **отдельный следующий патч к runner** и
интеграция функций постобработки/огибающих из основной Arbac.

Данных smoke-прогона (одна задача) недостаточно для проверки полноты
статистических выводов: C1/C5, медианы и P5/P95 пока не описывают
популяцию разных последовательностей. Научная статистика требует
полного JSON с разными классами и параметрами.

## Проверки

В среде подготовки: **24 теста прошло, 1 Parquet-тест пропущен** (`pyarrow`
недоступен в этой среде). В твоей Windows-среде v1 дал **13 прошедших тестов**, 
и полный цикл JSON → Parquet → GUI ранее успешно отработал.
После распаковки v2 локально нужно заново запустить тесты, чтобы подтвердить
тест Parquet с установленным `pyarrow` и обновление `summary.parquet`.
