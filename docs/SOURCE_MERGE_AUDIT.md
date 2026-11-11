# Отчёт по интеграции локального Arbac в исследовательскую оболочку

## Проверенная базовая ревизия

- Ветка Github: `DarkLordRowan/arbac`, `Magister`, commit `d2ab4993440b3e2b1ba53a060c91a121c2a0bf19`, 2026-11-01.
- Предоставленная локальная база: `ARBAC_LOCAL_SOURCE_FOR_REVIEW.zip`, 277 файлов, 103 Python-модуля внутри `arbacc`, 122 регистраций плагинов, из них **40 ускорителей**.
- Исследовательский модуль: Research v3 (отдельный анализ Parquet, JSON CLI/GUI, профилирование и события ошибок).

## Появившиеся локально алгоритмические модули относительно GitHub Magister

16 новых файлов в `arbacc/accelerators/`:

```
_generalized_models.py
_shanks_rank_guard.py
brezinski_e_general.py
cnct_weniger.py
cvz_2000.py
euler_alternating.py
ford_sidi_wm_1987.py
levin_power_remainder.py
levin_sidi_s.py
osada_extended.py
osada_rho.py
sidi_d_m.py
sidi_d_m_e_recursive.py
sidi_dm_strided.py
weniger_fractional_factorial.py
weniger_m_alias.py
```

Из уже существующих в GitHub файлов `arbacc/accelerators/direct.py` **изменён** в локальном архиве (другой Git blob SHA). Остальные файлы ядра не объявляются без изменений, пока не завершено полное пофайловое сравнение Git-дерева с архивом.

## Принципиальное математическое предупреждение

`levin_sidi_s` — отдельный идентификатор, но docstring прямо предупреждает, что это форма факториального преобразования, математически совпадающая с `weniger` при одинаковом `omega_n`, `beta` и порядке. Самостоятельность метода «Sidi S» по первоисточнику не доказана. Это **не ошибка арифметической реализации**, но существенное замечание о правильном названии и независимости методов в статье.

## Пакет, подготовленный в этом диалоге

- Все исходные файлы пользовательского архива сохранены в полном кандидате.
- Добавлены Research v3 и оболочка проверки на Windows.
- Обновлена полнота реестра в `tests/test_mathematical_oracles.py`: `levin_sidi_s` теперь ожидаем.
- Добавлен `tests/test_levin_sidi_s_oracle.py`, 121 тест, независимые точные дроби.
- Дополнительные результаты Stage C/E (полные JSON конфиги, логи и массивы Parquet) **не присутствуют** в загруженном архиве — они нужны отдельно, чтобы строго воспроизвести таблицы тезисов.
- Никаких изменений GitHub, commit, push в этой итерации не выполнялось.

## Локальная проверка

- Исследовательская часть и S-тесты: 156 passed, 1 skipped (pyarrow).
- Остальные математические тесты без недоступных зависимостей: 2463 passed, 44 skipped, 43 deselected.
- Полный Windows прогон должен выполнить `VERIFY_LOCAL_INTEGRATION.ps1`.
