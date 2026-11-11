"""Independent Tk GUI for launching runs and viewing compatible Parquet.

The analysis pane never imports Arbac or calls its runner. It can be used even
on a separate machine that has only mpmath, matplotlib and pyarrow installed.
"""
from __future__ import annotations
import csv
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .metrics import aggregate_summaries, number
from .analysis import load_or_analyze, save_csv
from .storage import iterate_tasks

# The tables show *observed data*, not heuristic composite ranks.
# Fields that need operator profiling / filter-event capture are marked N/A.
METRIC_GROUP_SECTIONS = {
    "Точность": [
        "tasks", "cases", "comparable", "c1", "c5", "c1_share", "c5_share",
        "median_gain_orders", "mean_gain_orders", "min_gain_orders", "max_gain_orders",
        "p05_gain_orders", "p95_gain_orders", "median_last_gain_orders",
        "median_cpp_orders_gain", "median_best_error", "median_last_error",
        "median_last_best_loss_orders", "median_step_better_share",
    ],
    "Достижение ε": [
        "tasks", "cases", "successful_acceleration_cases", "epsilon_reached_cases",
        "epsilon_earlier_cases", "median_epsilon_saved_terms", "median_best_n",
        "median_last_n", "median_n_accel_valid",
    ],
    "Робастность": [
        "tasks", "cases", "uncomparable_cases", "cases_with_failure", "failed",
        "failure_share", "division_zero_failures", "one_sided_cases",
        "nonincreasing_error_cases", "median_sign_changes", "median_error_increases",
        "median_error_increase_share",
    ],
    "Операции и события": [
        "tasks", "tasks_with_profile", "profiled_steps", "profile_modes",
        "op_add", "op_mul", "op_div", "op_neg", "op_special", "op_total",
        "median_op_total_per_profiled_task", "step_failures", "events_recorded",
        "median_division_zero_first_n", "median_step_elapsed_ms_sum",
    ],
    "Скорость": [
        "tasks", "cases", "median_elapsed_ms", "mean_elapsed_ms",
        "min_elapsed_ms", "max_elapsed_ms", "median_best_n", "median_last_n",
        "median_n_accel_valid",
    ],
    "Все показатели": [],
}

# Descriptions also appear on a separate tab, and in individual task passports.
METRIC_HELP = {
    "gain_best_orders": ("G_best, порядки", "log10(ошибка базовой при m_best / минимальная ошибка метода). Выбор m_best по истинному пределу: оракул."),
    "gain_last_orders": ("G_last, порядки", "То же сравнение ошибок при одинаковом бюджете, но для последнего корректного шага."),
    "cpp_orders_gain_vs_series_min": ("C++ ordersGains", "log10(min ошибки исходной траектории / min ошибки метода). Числа членов могут различаться."),
    "cpp_relative_error_vs_series_min": ("C++ relativeErrors", "min ошибки метода / min ошибки исходной траектории (не относительная ошибка к |S|)."),
    "cpp_amp_at_best_n_orders": ("C++ ampAtMinN", "Выигрыш в порядках относительно исходной последовательности при m лучшего шага метода."),
    "cpp_step_series_amp_mean_orders": ("C++ avgStepSeriesAmp", "Среднее log10(|S_m-S|/|A_m-S_m|) по сравнимым шагам; НЕ то же, что выигрыш точности."),
    "cpp_step_series_amp_median_orders": ("C++ medianStepSeriesAmp", "Медиана log10(|S_m-S|/|A_m-S_m|) по шагам."),
    "cpp_step_series_amp_worst_orders": ("C++ worstStepSeriesAmp", "Минимальное значение log10(|S_m-S|/|A_m-S_m|) по шагам."),
    "step_gain_mean_orders": ("Средний G по шагам", "Средний log10(|S_m-S|/|A_m-S|) по всем сравнимым шагам."),
    "step_gain_median_orders": ("Медиана G по шагам", "Медиана выигрыша при равном бюджете на каждом шаге."),
    "step_gain_min_orders": ("Худший G по шагам", "Минимальный выигрыш в порядках среди сравнимых шагов."),
    "step_gain_max_orders": ("Лучший G по шагам", "Максимальный выигрыш в порядках среди сравнимых шагов."),
    "c1": ("C1", "1, если лучший шаг метода уменьшил абсолютную ошибку не менее чем в 10 раз при том же числе входных членов."),
    "c5": ("C5", "1, если уменьшение ошибки составило не менее 10^5 раз."),
    "successful_acceleration": ("Успешное ускорение", "Если база достигла ε: ускоритель раньше. Если нет: лучший шаг метода точнее базы при том же m; это ретроспективный критерий."),
    "epsilon_earlier": ("Достиг ε раньше", "1, если ускоритель впервые достиг ε раньше исходной последовательности в сохранённом бюджете."),
    "base_first_epsilon_n": ("ε: база", "Первое число членов, при котором |S_m-S| < ε."),
    "accel_first_epsilon_n": ("ε: метод", "Первое число исходных членов, при котором |A_m-S| < ε."),
    "epsilon_saved_terms": ("Экономия членов", "m_base(ε)-m_method(ε). Определено, если оба достигли ε."),
    "best_n": ("m лучшего шага", "Число фактически использованных исходных членов на лучшем шаге."),
    "last_n": ("m последнего шага", "Число фактически использованных членов на последнем корректном шаге."),
    "best_error": ("Минимальная ошибка", "Минимальная абсолютная ошибка метода на сохранённой траектории."),
    "last_error": ("Последняя ошибка", "Абсолютная ошибка последнего корректного шага."),
    "last_best_loss_orders": ("Потеря после лучшего", "log10(последняя ошибка / минимальная ошибка). Неотрицательно."),
    "relative_error_best": ("Отн. ошибка к пределу", "min |A_m-S| / |S|. Не определена при S=0."),
    "base_min_error": ("Мин. ошибка базы", "Минимальная абсолютная ошибка исходной последовательности на сохранённом отрезке."),
    "n_steps_comparable": ("Сравнимые шаги", "Число шагов ускорителя, для которых имеется исходное приближение с тем же m."),
    "step_better_share": ("Доля улучшений", "Доля сравнимых шагов, на которых абсолютная ошибка метода меньше ошибки базы."),
    "sign_changes": ("Смены знака", "Число смен знака A_m-S; только для вещественных последовательностей."),
    "one_sided": ("Односторонняя", "1, если на всех ненулевых ошибках знак постоянный. Не применимо к комплексным последовательностям."),
    "error_monotonicity": ("Монотонность ошибки", "Тип наблюдаемой траектории абсолютной ошибки: рост, спад, постоянная либо немонотонная."),
    "error_increases": ("Нарушения невозрастания", "Число переходов к большей абсолютной ошибке."),
    "error_increase_share": ("Доля увеличений", "Число увеличений ошибки / число переходов между корректными шагами."),
    "division_zero_failure": ("Деление на ноль", "1 при выявленной ошибке деления на ноль в статусе завершения."),
    "elapsed_ms": ("Время, мс", "Время вычисления ускорителя в runner, без последующего анализа и записи Parquet."),
    "op_add": ("Сложения и вычитания", "Количество вызовов add/sub через ctx.backend внутри accelerator.step; НЕ реальные машинные операции и НЕ напрямую C++ profiling."),
    "op_mul": ("Умножения", "Количество вызовов ctx.backend.mul внутри accelerator.step, только при profile_backend_ops=true."),
    "op_div": ("Деления", "Количество вызовов ctx.backend.div внутри accelerator.step, включая ошибочные вызовы."),
    "op_neg": ("Смена знака", "Количество вызовов ctx.backend.neg внутри accelerator.step."),
    "op_special": ("Специальные вызовы", "Количество вызовов pow/sqrt/log/exp/тригонометрических и др. через ctx.backend. Это не цена их внутренней реализации."),
    "op_total": ("Всего учтённых API-вызовов", "Сумма категорий. Не охватывает прямые вызовы mpmath или внутренние операции backend."),
    "profile_mode": ("Режим профилирования", "backend_api_step_only: считаются только вызовы backend внутри accelerator.step. Не сравнивать с C++ как одинаковые операции."),
    "n_profiled_steps": ("Измеренных шагов", "Число успешных и неуспешных вызовов accelerator.step с включённым счётчиком."),
    "step_elapsed_ms_sum": ("Сумма времени шагов", "Время, проведённое внутри accelerator.step, без генерации исходных членов, запуска и записи Parquet."),
    "step_elapsed_ms_median": ("Медианное время шага", "Медиана длительностей корректных шагов ускорителя."),
    "n_events": ("События", "Число сохранённых событий step_failure и runner_stop."),
    "n_step_failures": ("Исключения в шагах", "Число зафиксированных исключений внутри accelerator.step."),
    "stop_reason": ("Причина остановки", "Сохранённый runner_stop: достижение бюджета, criterion либо исключение."),
    "filter_trigger_n": ("Фильтр: первый триггер", "Нет событий фильтров в trace v1; будет доступно при интеграции постобработки."),
    "division_zero_first_n": ("Первое деление на ноль", "При наличии v3-события step_failure — число использованных членов на первом зафиксированном ZeroDivisionError."),
    "division_zero_recovered": ("Восстановление после срыва", "1, если после события был поздний корректный шаг; текущий runner на исключении останавливается."),
}


METRIC_HELP.update({
    "reference_available": ("Известен предел", "1, если в Parquet есть пригодный эталон S для вычисления ошибок."),
    "n_accel_valid": ("Корректных шагов метода", "Число сохранённых конечных приближений ускорителя."),
    "n_baseline_valid": ("Корректных шагов базы", "Число сохранённых конечных исходных приближений."),
    "n_points_invalid": ("Некорректных точек", "Число строк без конечного числового значения (в пределах сохранённого набора)."),
    "n_steps_better": ("Лучше базы", "Число сравнимых шагов с меньшей абсолютной ошибкой ускорителя."),
    "n_steps_worse": ("Хуже базы", "Число сравнимых шагов с большей абсолютной ошибкой ускорителя."),
    "n_steps_equal": ("Равно базе", "Число сравнимых шагов с равной абсолютной ошибкой."),
    "best_k": ("k лучшего шага", "Внутренний индекс итерации/порядок, сохранённый ускорителем при наилучшем значении."),
    "last_k": ("k последнего шага", "Внутренний индекс последнего корректного шага."),
    "base_last_error": ("Последняя ошибка базы", "Ошибка на последнем сохранённом исходном приближении."),
    "base_error_at_best_n": ("База на m_best", "Ошибка базы при числе входных членов, использованных для лучшего шага метода."),
    "base_error_at_last_n": ("База на m_last", "Ошибка базы на последнем корректном шаге метода при равном числе членов."),
    "base_reached_epsilon": ("База достигла ε", "1, если исходная последовательность достигла ε в сохранённом бюджете."),
    "accel_reached_epsilon": ("Метод достиг ε", "1, если ускоритель достиг ε в сохранённом бюджете."),
    "error_decreases": ("Уменьшения ошибки", "Число переходов к меньшей абсолютной ошибке."),
    "error_equals": ("Постоянная ошибка", "Число последовательных пар корректных шагов с равной абсолютной ошибкой."),
    "side_type": ("Сторонность", "one_sided / two_sided; для комплексных траекторий неизвестна."),
    "failure_category": ("Тип отказа", "Классификация ошибки по сообщению; не доказывает математическую причину отказа."),
})


class ResearchGUI(tk.Tk):
    def __init__(self, dataset=None):
        super().__init__()
        self.title("Arbac — исследования: JSON-прогоны и независимый Parquet-анализ")
        self.geometry("1270x820")
        self.minsize(940,600)
        self.info_queue=queue.Queue()
        self.summaries=[]
        self.filtered=[]
        self.current_path=tk.StringVar(value=str(dataset or ""))
        self.current_epsilon=tk.StringVar(value="1e-8")
        self.current_mapping=tk.StringVar(value="")
        self.current_config=tk.StringVar(value="")
        self.current_output=tk.StringVar(value="out/research_run")
        self.workers=tk.StringVar(value="8")
        self.profile_ops=tk.BooleanVar(value=False)
        self.current_group=tk.StringVar(value="method_id,backend,dps")
        self.run_proc=None
        self.metric_section=tk.StringVar(value="Точность")
        self.per_task=tk.BooleanVar(value=False)
        notebook=ttk.Notebook(self)
        notebook.pack(fill="both",expand=True,padx=8,pady=8)
        self.tab_run=ttk.Frame(notebook)
        self.tab_view=ttk.Frame(notebook)
        notebook.add(self.tab_run,text="1. Запуск из JSON")
        notebook.add(self.tab_view,text="2. Анализ готового Parquet")
        self.build_run()
        self.build_view()
        self.after(100,self.poll)
        if dataset:
            self.after(300,self.start_analysis)

    def build_run(self):
        parent=self.tab_run
        row=ttk.Frame(parent);row.pack(fill="x",padx=8,pady=8)
        ttk.Label(row,text="Конфигурация JSON:").pack(side="left")
        ttk.Entry(row,textvariable=self.current_config,width=75).pack(side="left",fill="x",expand=True,padx=6)
        ttk.Button(row,text="Обзор…",command=self.pick_config).pack(side="left")
        row=ttk.Frame(parent);row.pack(fill="x",padx=8,pady=5)
        ttk.Label(row,text="Каталог результатов:").pack(side="left")
        ttk.Entry(row,textvariable=self.current_output,width=69).pack(side="left",fill="x",expand=True,padx=6)
        ttk.Button(row,text="Обзор…",command=self.pick_output).pack(side="left")
        row=ttk.Frame(parent);row.pack(fill="x",padx=8,pady=8)
        ttk.Label(row,text="Процессы:").pack(side="left")
        ttk.Spinbox(row,from_=1,to=128,textvariable=self.workers,width=5).pack(side="left",padx=6)
        self.start_btn=ttk.Button(row,text="Запустить (с возобновлением)",command=self.start_run)
        self.start_btn.pack(side="left",padx=8)
        ttk.Checkbutton(row,text="Считать вызовы backend API (медленнее)",variable=self.profile_ops).pack(side="left",padx=7)
        ttk.Label(parent,text="Запись выполняется напрямую в сжатые Parquet-части. Результаты можно открывать независимо от этого окна.",wraplength=1040).pack(anchor="w",padx=12,pady=7)
        self.log=tk.Text(parent,wrap="word",height=20,font=("Consolas",10))
        self.log.pack(fill="both",expand=True,padx=8,pady=8)

    def build_view(self):
        parent=self.tab_view
        row=ttk.Frame(parent);row.pack(fill="x",padx=8,pady=6)
        ttk.Label(row,text="Parquet / каталог:").pack(side="left")
        ttk.Entry(row,textvariable=self.current_path,width=75).pack(side="left",fill="x",expand=True,padx=6)
        ttk.Button(row,text="Файл…",command=self.pick_file).pack(side="left",padx=2)
        ttk.Button(row,text="Папка…",command=self.pick_folder).pack(side="left")
        row=ttk.Frame(parent);row.pack(fill="x",padx=8,pady=5)
        ttk.Label(row,text="Порог ε:").pack(side="left")
        ttk.Entry(row,textvariable=self.current_epsilon,width=13).pack(side="left",padx=5)
        ttk.Label(row,text="Группы:").pack(side="left",padx=7)
        group_combo=ttk.Combobox(row,textvariable=self.current_group,width=27,
                     values=["method_id,backend,dps","class_id,method_id","series_id,method_id","backend,dps","accel_id"],
                     state="normal")
        group_combo.pack(side="left",padx=6)
        group_combo.bind("<<ComboboxSelected>>",lambda _e:self.display_results() if self.summaries else None)
        self.analyze_btn=ttk.Button(row,text="Анализировать",command=self.start_analysis)
        self.analyze_btn.pack(side="left",padx=8)
        ttk.Button(row,text="График выбранной задачи",command=self.show_trace).pack(side="left",padx=3)
        ttk.Button(row,text="CSV…",command=self.export_csv).pack(side="left",padx=3)
        row=ttk.Frame(parent);row.pack(fill="x",padx=8,pady=4)
        ttk.Label(row,text="Схема колонок (необязательно):").pack(side="left")
        ttk.Entry(row,textvariable=self.current_mapping,width=45).pack(side="left",padx=6)
        ttk.Button(row,text="JSON mapping…",command=self.pick_mapping).pack(side="left")
        self.status=ttk.Label(parent,text="Готово. Можно открыть любой совместимый Parquet, созданный в другой сессии или на другом компьютере.")
        self.status.pack(anchor="w",padx=8,pady=4)
        ttk.Checkbutton(parent,text="Считать каждую конфигурацию отдельно (иначе лучший параметр по каждому случаю — оракул)",
                        variable=self.per_task,command=self.display_results).pack(anchor="w",padx=8)
        self.analysis_tabs=ttk.Notebook(parent)
        self.analysis_tabs.pack(fill="both",expand=True,padx=8,pady=4)
        overview=ttk.Frame(self.analysis_tabs)
        detailed=ttk.Frame(self.analysis_tabs)
        passport=ttk.Frame(self.analysis_tabs)
        definitions=ttk.Frame(self.analysis_tabs)
        events_tab=ttk.Frame(self.analysis_tabs)
        self.analysis_tabs.add(overview,text="Обзор")
        self.analysis_tabs.add(detailed,text="Все групповые метрики")
        self.analysis_tabs.add(passport,text="Паспорт выбранной задачи")
        self.analysis_tabs.add(events_tab,text="События задачи")
        self.analysis_tabs.add(definitions,text="Определения и ограничения")
        p=ttk.PanedWindow(overview,orient="vertical")
        p.pack(fill="both",expand=True)
        groups=ttk.Labelframe(p,text="Сводка по методам / классам")
        cases=ttk.Labelframe(p,text="Задачи — выбери строку для паспорта или графика")
        p.add(groups,weight=2);p.add(cases,weight=3)
        self.group_tree=self.table(groups,
                ("group","tasks","cases","comp","c1","c5","success","eps","failed","gain","lastgain","time"),
                ("Группа","Конфигов","Случаев","Сравнимо","C1","C5","Успешно","Достигли ε","Отказов","Мед. G","Мед. G_last","Время, мс"))
        self.case_tree=self.table(cases,
                ("task","method","series","dps","status","best","last","gain","lastgain","eps","sign","mono","time"),
                ("Task ID","Метод","Последовательность","dps","Статус","Луч. ош.","Посл. ош.","G_best","G_last","Экономия N","Смены знака","Ошибка","мс"))
        self.case_tree.bind("<<TreeviewSelect>>",lambda _e:self.show_task_passport())
        self.case_tree.bind("<Double-1>",lambda _e:self.analysis_tabs.select(passport))
        line=ttk.Frame(detailed);line.pack(fill="x",padx=6,pady=6)
        ttk.Label(line,text="Показатели:").pack(side="left")
        combo=ttk.Combobox(line,textvariable=self.metric_section,state="readonly",
                           values=list(METRIC_GROUP_SECTIONS),width=23)
        combo.pack(side="left",padx=5)
        combo.bind("<<ComboboxSelected>>",lambda _e:self.display_detailed())
        ttk.Label(line,text="Прокрутка таблицы по горизонтали; CSV содержит все поля.").pack(side="left",padx=9)
        self.detailed_tree=self.table(detailed,("group",),("Группа",))
        ttk.Label(passport,text="Нажми на задачу в разделе «Обзор». NULL означает отсутствие данных, а не нулевое значение.",
                  wraplength=1050).pack(anchor="w",padx=8,pady=5)
        self.passport_tree=self.table(passport,("field","value","meaning"),("Показатель","Значение","Смысл / оговорка"))
        self.passport_tree.column("field",width=280)
        self.passport_tree.column("value",width=300)
        self.passport_tree.column("meaning",width=900)
        ttk.Button(events_tab,text="Загрузить события выбранной задачи",command=self.show_task_events).pack(anchor="w",padx=8,pady=7)
        self.events_tree=self.table(events_tab,("n_used","k","event_type","event_message"),
             ("Использовано членов","Шаг","Событие","Описание"))
        self.events_tree.column("event_message",width=900)
        ttk.Label(definitions,text="Метрики C++ и тезиса НЕ смешиваются. Счётчики backend API доступны только при profile_backend_ops=true; события фильтров пока не записываются. Нет данных ≠ ноль.",
                  wraplength=1100).pack(anchor="w",padx=8,pady=5)
        self.definitions_tree=self.table(definitions,("name","title","info"),("Ключ","Русское название","Описание"))
        self.definitions_tree.column("name",width=320)
        self.definitions_tree.column("title",width=235)
        self.definitions_tree.column("info",width=960)
        for k,(label,meaning) in METRIC_HELP.items():
            self.definitions_tree.insert("","end",values=(k,label,meaning))
        ttk.Label(parent,text="Все метрики пересчитываются только по Parquet: без Arbac и без повторного прогона. Лучшие шаги и параметры выбираются ретроспективно по известному пределу.",
                  wraplength=1220).pack(anchor="w",padx=8,pady=4)

    @staticmethod
    def table(parent,fields,headers):
        outer=ttk.Frame(parent);outer.pack(fill="both",expand=True)
        tree=ttk.Treeview(outer,columns=fields,show="headings",selectmode="browse")
        for col,label in zip(fields,headers):
            tree.heading(col,text=label)
            tree.column(col,width=(300 if col in ("task","group") else 108),anchor="w")
        ys=ttk.Scrollbar(outer,orient="vertical",command=tree.yview)
        xs=ttk.Scrollbar(outer,orient="horizontal",command=tree.xview)
        tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        tree.grid(row=0,column=0,sticky="nsew")
        ys.grid(row=0,column=1,sticky="ns");xs.grid(row=1,column=0,sticky="ew")
        outer.rowconfigure(0,weight=1);outer.columnconfigure(0,weight=1)
        return tree

    def pick_config(self):
        v=filedialog.askopenfilename(filetypes=[("JSON", "*.json")]);
        if v:self.current_config.set(v)

    def pick_output(self):
        v=filedialog.askdirectory();
        if v:self.current_output.set(v)

    def pick_file(self):
        v=filedialog.askopenfilename(filetypes=[("Parquet", "*.parquet")]);
        if v:self.current_path.set(v)

    def pick_folder(self):
        v=filedialog.askdirectory();
        if v:self.current_path.set(v)

    def pick_mapping(self):
        v=filedialog.askopenfilename(filetypes=[("JSON", "*.json")]);
        if v:self.current_mapping.set(v)

    def start_run(self):
        config=self.current_config.get().strip()
        output=self.current_output.get().strip()
        if not Path(config).is_file() or not output:
            messagebox.showerror("Ошибка","Выбери существующий JSON и каталог результатов")
            return
        try:workers=int(self.workers.get()); assert workers>0
        except (ValueError,AssertionError):
            messagebox.showerror("Ошибка","Число процессов должно быть положительным")
            return
        cmd=[sys.executable,"-u","-m","arbac_research","run",config,
             "--output",output,"--workers",str(workers)]
        if self.profile_ops.get(): cmd.append("--profile-ops")
        self.log.insert("end","\n> "+" ".join(cmd)+"\n");self.log.see("end")
        self.start_btn.configure(state="disabled")
        def go():
            try:
                # text streaming from stdout; Arbac runs in another process
                self.run_proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                               text=True,bufsize=1,encoding="utf-8",errors="replace")
                for line in self.run_proc.stdout:
                    self.info_queue.put(("log",line))
                code=self.run_proc.wait()
                self.info_queue.put(("run_done",code))
            except Exception as e:
                self.info_queue.put(("error",f"Ошибка запуска: {e}"))
                self.info_queue.put(("run_done",1))
        threading.Thread(target=go,daemon=True).start()

    def start_analysis(self):
        path=self.current_path.get().strip()
        if not Path(path).exists():
            messagebox.showerror("Ошибка","Выбери существующий Parquet-файл или каталог")
            return
        eps=self.current_epsilon.get().strip()
        mapping=self.current_mapping.get().strip()
        self.analyze_btn.configure(state="disabled")
        self.status.configure(text="Анализ Parquet... Алгоритмы Arbac не запускаются.")
        def go():
            try:
                import json
                spec=json.loads(Path(mapping).read_text(encoding="utf-8")) if mapping else None
                results=load_or_analyze(path,epsilon=eps,mapping=spec)
                self.info_queue.put(("analysis_done",results))
            except Exception as e:
                self.info_queue.put(("analysis_error",str(e)))
        threading.Thread(target=go,daemon=True).start()

    def poll(self):
        try:
            while True:
                action,value=self.info_queue.get_nowait()
                if action=="log":
                    self.log.insert("end",value);self.log.see("end")
                elif action=="run_done":
                    self.start_btn.configure(state="normal")
                    self.log.insert("end",f"\nЗавершено, код {value}. Можно открыть каталог в 'Анализ Parquet'.\n")
                    self.log.see("end")
                elif action=="error":messagebox.showerror("Arbac",value)
                elif action=="analysis_error":
                    self.analyze_btn.configure(state="normal")
                    self.status.configure(text="Ошибка анализа")
                    messagebox.showerror("Анализ",value)
                elif action=="analysis_done":
                    self.analyze_btn.configure(state="normal")
                    self.summaries=value
                    self.status.configure(text=f"Загружено {len(value)} задач. Никаких пересчётов алгоритмов не выполнялось.")
                    self.display_results()
        except queue.Empty:
            pass
        self.after(100,self.poll)

    @staticmethod
    def short(value,limit=18):
        if value is None:return "—"
        s=str(value)
        return s if len(s)<limit else s[:limit-1]+"…"

    def display_results(self):
        if not hasattr(self,"group_tree"):
            return
        for t in (self.case_tree,self.group_tree):
            for k in t.get_children():t.delete(k)
        group=[x.strip() for x in self.current_group.get().split(",") if x.strip()]
        self.aggregated=aggregate_summaries(self.summaries,group,per_task=self.per_task.get())
        for i,record in enumerate(self.aggregated):
            values=(" | ".join(str(record.get(k) if record.get(k) is not None else "—") for k in group),
                   record.get("tasks"),record.get("cases"),record.get("comparable"),record.get("c1"),
                   record.get("c5"),record.get("successful_acceleration_cases"),
                   record.get("epsilon_reached_cases"),record.get("failed"),
                   self.short(record.get("median_gain_orders"),15),
                   self.short(record.get("median_last_gain_orders"),15),
                   self.short(record.get("median_elapsed_ms"),15))
            self.group_tree.insert("", "end",iid=f"G{i}",values=values)
        for i,r in enumerate(self.summaries[:5000]):
            values=(r.get("task_id"),r.get("accel_id"),r.get("series_id"),
                    r.get("dps"),r.get("status"),self.short(r.get("best_error")),
                    self.short(r.get("last_error")),self.short(r.get("gain_best_orders")),
                    self.short(r.get("gain_last_orders")),r.get("epsilon_saved_terms"),
                    r.get("sign_changes"),r.get("error_monotonicity"),
                    self.short(r.get("elapsed_ms"),11))
            self.case_tree.insert("","end",iid=f"T{i}",values=values)
        self.display_detailed()
        for k in self.passport_tree.get_children():self.passport_tree.delete(k)

    def display_detailed(self):
        if not hasattr(self,"detailed_tree"):
            return
        group=[x.strip() for x in self.current_group.get().split(",") if x.strip()]
        section=self.metric_section.get()
        wanted=METRIC_GROUP_SECTIONS.get(section,[])
        if not wanted:
            wanted=[x for x in (list(self.aggregated[0]) if getattr(self,"aggregated",[]) else []) if x not in group]
        fields=["group"]+wanted
        tree=self.detailed_tree
        tree.configure(columns=fields)
        for f in fields:
            tree.heading(f,text="Группа" if f=="group" else f)
            tree.column(f,width=260 if f=="group" else max(125,min(265,len(f)*9)),anchor="w",stretch=False)
        for iid in tree.get_children():tree.delete(iid)
        for idx,r in enumerate(getattr(self,"aggregated",[])):
            values=[" | ".join(str(r.get(k) if r.get(k) is not None else "—") for k in group)]
            values += [self.short(r.get(c),40) for c in wanted]
            tree.insert("","end",iid=f"D{idx}",values=values)

    def show_task_passport(self):
        if not hasattr(self,"passport_tree"):
            return
        for iid in self.passport_tree.get_children():self.passport_tree.delete(iid)
        sel=self.case_tree.selection()
        if not sel:return
        idx=int(sel[0][1:])
        if idx>=len(self.summaries):return
        summary=self.summaries[idx]
        for key,value in summary.items():
            meaning=METRIC_HELP.get(key,(key,""))[1]
            self.passport_tree.insert("","end",values=(key,self.short(value,100),meaning))

    def export_csv(self):
        if not self.summaries:
            messagebox.showwarning("Нет данных","Сначала загрузи результаты")
            return
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV", "*.csv")])
        if path:save_csv(path,self.summaries)

    def _selected_task_rows(self):
        sel=self.case_tree.selection()
        if not sel:
            return None
        idx=int(sel[0][1:])
        if idx >= len(self.summaries):return None
        summary=self.summaries[idx]
        source=summary.get("source_file")
        if not source:return None
        file=Path(source)
        if not file.is_file():
            file=Path(self.current_path.get().strip()) / source
        if not file.is_file():return None
        import json
        mpfile=self.current_mapping.get().strip()
        spec=json.loads(Path(mpfile).read_text(encoding="utf-8")) if mpfile else None
        for records in iterate_tasks(file,mapping=spec):
            if str(records[0].get("task_id")) == summary["task_id"]:
                return records
        return None

    def show_task_events(self):
        for iid in self.events_tree.get_children():self.events_tree.delete(iid)
        records=self._selected_task_rows()
        if records is None:
            messagebox.showinfo("События", "Выбери задачу в таблице «Обзор»")
            return
        for index,r in enumerate(records):
            if r.get("row_type") == "event":
                self.events_tree.insert("","end",iid=str(index),values=(
                   r.get("n_used"),r.get("k"),r.get("event_type"),r.get("event_message")))

    def show_trace(self):
        sel=self.case_tree.selection()
        if not sel:
            messagebox.showinfo("График","Выбери отдельную задачу в нижней таблице")
            return
        index=int(sel[0][1:]); row=self.summaries[index]
        file=row.get("source_file")
        if file and not Path(file).exists() and not Path(file).is_absolute():
            file=str(Path(self.current_path.get().strip())/file)
        if not file or not Path(file).exists():
            messagebox.showerror("Ошибка","Исходный Parquet-файл недоступен")
            return
        wanted=row["task_id"]
        task_rows=None
        import json
        mpfile=self.current_mapping.get().strip()
        spec=json.loads(Path(mpfile).read_text(encoding="utf-8")) if mpfile else None
        for records in iterate_tasks(file,mapping=spec):
            if str(records[0].get("task_id"))==wanted:
                task_rows=records
                break
        if not task_rows:
            messagebox.showerror("Ошибка","Не удалось найти траекторию")
            return
        try:
            import mpmath as mp
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg,NavigationToolbar2Tk
            dps=max(50,int(row.get("dps") or 50)+20)
            with mp.workdps(dps):
                exact=number(task_rows[0].get("exact_sum"))
                if exact is None:
                    messagebox.showinfo("График","Неизвестен предел: логарифм абсолютной ошибки недоступен")
                    return
                a=[],[];b=[],[]
                for r in task_rows:
                    value=number(r.get("value"))
                    if value is None:continue
                    error=abs(value-exact)
                    log=float(mp.log10(error)) if error!=0 else -dps
                    if r.get("row_type","accel")=="baseline":
                        b[0].append(int(r.get("n_used") or 0));b[1].append(log)
                    else:
                        a[0].append(int(r.get("n_used") or 0));a[1].append(log)
            win=tk.Toplevel(self);win.title(f"Ошибка по числу использованных членов — {wanted}")
            win.geometry("920x580")
            fig=Figure(figsize=(9,5),dpi=100);ax=fig.add_subplot(111)
            if b[0]:ax.plot(b[0],b[1],label="Исходная последовательность")
            if a[0]:ax.plot(a[0],a[1],marker=".",label="Ускоренное приближение")
            ax.set_xlabel("Число использованных членов m")
            ax.set_ylabel("log10(|приближение − предел|)")
            ax.grid(True);ax.legend()
            canvas=FigureCanvasTkAgg(fig,master=win)
            canvas.get_tk_widget().pack(fill="both",expand=True)
            toolbar=NavigationToolbar2Tk(canvas,win);toolbar.update()
            canvas.draw()
        except Exception as e:
            messagebox.showerror("График",str(e))


def main_gui(dataset=None):
    ResearchGUI(dataset).mainloop()
