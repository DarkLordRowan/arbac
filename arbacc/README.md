# arbacc — ядро фреймворка

Здесь весь исполняемый код. Все модули импортируются как `arbacc.X`.

## Три принципа

1. **Плагин = один файл.** Новый ряд, шум, акселератор, критерий
   остановки, фильтр или огибающая — это один `.py` в нужной папке
   с декоратором `@register`. Ядро и GUI менять **не нужно**.

2. **PARAM_SPEC — единый источник правды.** Плагин объявляет один
   словарь `PARAM_SPEC`, из которого автоматически выводятся:
   значения по умолчанию, обязательные параметры, валидация,
   спецификация для GUI, короткие метки для легенд.

3. **Слои разделены.** Ядро не знает про GUI. GUI не знает про
   конкретные плагины — обращается через реестр.

## Структура

    arbacc/
      core/         контракты, PluginBase, реестр, RNG
      precision/    адаптеры длинной арифметики (mpmath, arb)
      series/       источники рядов
      noise/        модели шума
      accelerators/ алгоритмы ускорения
      stopping/     критерии остановки
      postprocess/  фильтры результата
      envelopes/    скользящие огибающие
      runner/       планировщик и исполнитель
      storage/      сохранение/загрузка
      cli.py        командная строка
      __main__.py   точка входа `python -m arbacc`

## Точка входа

Из корня проекта:

    python -m arbacc --config test.json        # запустить
    python -m arbacc validate test.json        # проверить
    python -m arbacc plan test.json            # построить план

Или явно:

    python -m arbacc run test.json
    python -m arbacc run test.json --skip-existing

## Навигация

| Хочу... | Смотреть |
|---|---|
| понять, как устроен плагин | `core/README.md` |
| добавить ряд | `series/README.md` |
| добавить шум | `noise/README.md` |
| добавить акселератор | `accelerators/README.md` |
| добавить критерий остановки | `stopping/README.md` |
| добавить фильтр | `postprocess/README.md` |
| добавить огибающую | `envelopes/README.md` |
| разобраться с раннером | `runner/README.md` |
| понять формат output | `storage/README.md` |
| переключить backend | `precision/README.md` |
| запустить тесты | `../tests/README.md` |