"""
Загрузка данных из output для визуализации.

Зачем:
    View читает сохранённые артефакты (result.json, iterations.jsonl,
    manifest.json, summary.json) и превращает их в объекты для
    отображения.

    exact_sum вычисляется автоматически, если его нет в конфиге:
      1) явный из params.exact_sum,
      2) analytic_sum(ctx) — через backend (mpmath или arb).

    envelope_values (амплитуды огибающей по итерациям) — если
    сохранены в summary.json.

Как расширять:
    Если появятся новые артефакты (например, чекпоинты) — добавь
    загрузку и поле в AccelData.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# =====================================================================
# AccelData — все данные одной задачи
# =====================================================================

@dataclass
class AccelData:
    """Все данные одной задачи акселерации для отображения."""
    task_id: str
    series_id: str
    noise_id: str
    accel_id: str
    path: Path

    # Из manifest.json
    manifest: dict = field(default_factory=dict)
    input_payload: dict = field(default_factory=dict)

    # Из result.json
    accelerator: str = ""
    params: dict = field(default_factory=dict)
    estimate: str | None = None
    n_used: int = 0
    n_max: int | None = None
    stopped_by: str = ""
    status: str = ""
    error: str | None = None
    digits_gained: int | None = None

    # Из iterations.jsonl
    iterations: list[dict] = field(default_factory=list)

    # Из postprocess/{...}/filters/*/summary.json
    filters: dict = field(default_factory=dict)
    # Из postprocess/{...}/envelopes/*/summary.json
    envelopes: dict = field(default_factory=dict)

    # Точная сумма, если известна
    exact_sum: str | None = None

    # Амплитуды огибающих: {env_name: [float, ...]}
    envelope_values: dict = field(default_factory=dict)
    # Верхняя и нижняя границы огибающей: {env_name: [float, ...]}
    envelope_upper: dict = field(default_factory=dict)
    envelope_lower: dict = field(default_factory=dict)
    # Индексы k для амплитуд: {env_name: [int, ...]}
    envelope_indices: dict = field(default_factory=dict)

    # --- Читаемые имена (для легенд) ---------------------------------

    @property
    def short_label(self) -> str:
        """Короткая метка с dps."""
        dps = ""
        prec = self.input_payload.get("precision")
        if isinstance(prec, dict):
            d = prec.get("dps")
            if d is not None:
                dps = f"_dps{d}"
        return f"{self.series_id} / {self.noise_id} / {self.accel_id}{dps}"

    @property
    def series_display(self) -> str:
        """Читаемое имя серии: 'cos(x=0.6)'."""
        node = self.input_payload.get("series", {}) or {}
        return node_display_short("series", node)

    @property
    def noise_display(self) -> str:
        """Читаемое имя шума: 'gauss(sig=1e-6)' или 'none'."""
        node = self.input_payload.get("noise", {}) or {}
        return node_display_short("noise", node)

    @property
    def accel_display(self) -> str:
        """Читаемое имя акселератора: 'aitd2' или 'aitd2(ord=5)'."""
        node = self.input_payload.get("accelerator", {}) or {}
        return node_display_short("accelerator", node)

    @property
    def dps_suffix(self) -> str:
        """
        Суффикс ' [backend=arb, dps=30]' для легенды.

        Backend показывается всегда, если он не mpmath (дефолт).
        Так arb-кривые отличаются от mpmath-кривых.
        """
        prec = self.input_payload.get("precision")
        if not isinstance(prec, dict):
            return ""

        parts = []
        backend = prec.get("backend")
        if backend and backend != "mpmath":
            parts.append(f"backend={backend}")

        d = prec.get("dps")
        if d is not None:
            parts.append(f"dps={d}")

        if not parts:
            return ""
        return " [" + ", ".join(parts) + "]"

    def output_root(self) -> Path | None:
        """
        Корень output (директория с accel/ и postprocess/).

        Принимает:
            ничего.

        Возвращает:
            Path или None, если структура нестандартная.
        """
        p = self.path
        # path = out/accel/{s}/{n}/{a} — 4 уровня вверх.
        for _ in range(4):
            p = p.parent
        return p if p.exists() else None


# =====================================================================
# Короткие имена через реестр плагинов
# =====================================================================

#: Соответствие kind (в input_payload) → имя ключа в реестре.
_REGISTRY_KIND = {
    "series": "series",
    "noise": "noise",
    "accelerator": "accelerators",
    "postprocess": "postprocess",
    "envelope": "envelopes",
}


def _get_display_name(kind_in_payload: str, type_name: str) -> str:
    """
    Короткое имя плагина через реестр.

    Принимает:
        kind_in_payload — "series" | "noise" | "accelerator" | ...
        type_name       — имя типа ("cos", "gaussian", ...).

    Возвращает:
        строку.
    """
    kind = _REGISTRY_KIND.get(kind_in_payload)
    if not kind:
        return type_name
    try:
        # Импорт запускает autodiscovery — заполняет реестр.
        import arbacc.series        # noqa: F401
        import arbacc.noise         # noqa: F401
        import arbacc.accelerators  # noqa: F401
        import arbacc.stopping      # noqa: F401
        import arbacc.postprocess   # noqa: F401
        import arbacc.envelopes     # noqa: F401

        from arbacc.core.registry import get as _get
        Cls = _get(kind, type_name)
        return Cls.get_display_name()
    except Exception:
        return type_name


def _format_params_via_plugin(
    kind_in_payload: str,
    type_name: str,
    params: dict,
) -> str:
    """
    Короткое представление params через плагин.

    Принимает:
        kind_in_payload — категория.
        type_name       — имя типа.
        params          — словарь параметров.

    Возвращает:
        строку.
    """
    kind = _REGISTRY_KIND.get(kind_in_payload)
    if not kind:
        return ""
    try:
        import arbacc.series        # noqa: F401
        import arbacc.noise         # noqa: F401
        import arbacc.accelerators  # noqa: F401
        import arbacc.stopping      # noqa: F401
        import arbacc.postprocess   # noqa: F401
        import arbacc.envelopes     # noqa: F401

        from arbacc.core.registry import get as _get
        Cls = _get(kind, type_name)
        return Cls.format_short_params(params or {})
    except Exception:
        return ""


def node_display_short(kind_in_payload: str, node: dict) -> str:
    """
    Короткое читаемое имя узла: 'cos(x=0.6)', 'aitd2'.

    Принимает:
        kind_in_payload — "series" | "noise" | "accelerator" | ...
        node            — {'type': ..., 'params': {...}}.

    Возвращает:
        строку.
    """
    t = node.get("type", "?")
    display = _get_display_name(kind_in_payload, t)
    params_str = _format_params_via_plugin(
        kind_in_payload, t, node.get("params", {}) or {}
    )
    return f"{display}({params_str})" if params_str else display


def name_with_params_short(
    kind_in_payload: str,
    name: str,
    params: dict,
) -> str:
    """
    Короткое имя плагина с параметрами: 'kz(p2,w5)'.

    Принимает:
        kind_in_payload — категория.
        name            — имя типа.
        params          — параметры.

    Возвращает:
        строку.
    """
    display = _get_display_name(kind_in_payload, name)
    params_str = _format_params_via_plugin(
        kind_in_payload, name, params or {}
    )
    return f"{display}({params_str})" if params_str else display


# =====================================================================
# Разрешение exact_sum
# =====================================================================

def _resolve_exact_sum(
    series_type: str,
    series_params: dict,
    prec: dict,
) -> str | None:
    """
    Возвращает точную сумму как строку:
      1) явный exact_sum из params,
      2) analytic_sum через backend.

    Принимает:
        series_type   — "sin" | "cos" | "geometric" | "zeta" | ...
        series_params — params серии.
        prec          — {"backend": ..., "dps": ...}.

    Возвращает:
        строку или None.
    """
    explicit = series_params.get("exact_sum")
    if explicit:
        return str(explicit)
    try:
        # Импорт нужен, чтобы реестр плагинов был заполнен.
        import arbacc.series        # noqa: F401
        import arbacc.noise         # noqa: F401
        import arbacc.accelerators  # noqa: F401
        import arbacc.stopping      # noqa: F401
        import arbacc.postprocess   # noqa: F401
        import arbacc.envelopes     # noqa: F401

        from arbacc.core.registry import get as _get
        from arbacc.core.context import Context
        from arbacc.precision import get_backend

        backend_name = prec.get("backend", "mpmath") if isinstance(prec, dict) else "mpmath"
        dps = prec.get("dps", 30) if isinstance(prec, dict) else 30
        ctx = Context(backend=get_backend(backend_name), dps=dps)
        Cls = _get("series", series_type)
        s = Cls(params=series_params)
        v = s.exact_sum(ctx)
        if v is not None:
            return ctx.backend.to_str(v, dps)
    except Exception:
        pass
    return None


# =====================================================================
# Загрузка задач
# =====================================================================

def list_accel_tasks(output_root: Path) -> list[AccelData]:
    """
    Обходит output_root/accel/*/*/*/ и возвращает список задач.

    Принимает:
        output_root — корень output (например, out/exp_001).

    Возвращает:
        список AccelData.
    """
    accel_dir = output_root / "accel"
    if not accel_dir.exists():
        return []

    tasks: list[AccelData] = []
    for series_dir in sorted(accel_dir.iterdir()):
        if not series_dir.is_dir():
            continue
        for noise_dir in sorted(series_dir.iterdir()):
            if not noise_dir.is_dir():
                continue
            for accel_subdir in sorted(noise_dir.iterdir()):
                if not accel_subdir.is_dir():
                    continue
                result_path = accel_subdir / "result.json"
                if not result_path.exists():
                    continue
                data = _load_accel_data(accel_subdir)
                if data is not None:
                    tasks.append(data)
    return tasks


def _load_accel_data(accel_path: Path) -> AccelData | None:
    """
    Читает данные одной задачи.

    Принимает:
        accel_path — директория accel/{series}/{noise}/{accel}.

    Возвращает:
        AccelData или None, если result.json битый.
    """
    series_id = accel_path.parent.parent.name
    noise_id = accel_path.parent.name
    accel_id = accel_path.name
    task_id = f"{series_id}__{noise_id}__{accel_id}"

    try:
        result = json.loads(
            (accel_path / "result.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None

    data = AccelData(
        task_id=task_id,
        series_id=series_id,
        noise_id=noise_id,
        accel_id=accel_id,
        path=accel_path,
        accelerator=result.get("accelerator", ""),
        params=result.get("params", {}) or {},
        estimate=result.get("estimate"),
        n_used=int(result.get("n_used", 0)),
        n_max=result.get("n_max"),
        stopped_by=result.get("stopped_by", ""),
        status=result.get("status", "?"),
        error=result.get("error"),
        digits_gained=result.get("digits_gained"),
    )

    # manifest.json
    try:
        manifest = json.loads(
            (accel_path / "manifest.json").read_text(encoding="utf-8")
        )
        data.manifest = manifest
        data.input_payload = manifest.get("input", {}) or {}
    except (OSError, json.JSONDecodeError):
        pass

    # --- exact_sum ---
    series_input = data.input_payload.get("series", {}) or {}
    series_params = series_input.get("params", {}) or {}
    prec = data.input_payload.get("precision", {}) or {}
    exact = series_input.get("exact_sum") or series_params.get("exact_sum")
    if exact is None:
        exact = _resolve_exact_sum(
            series_input.get("type", ""),
            series_params,
            prec,
        )
    data.exact_sum = exact

    # --- iterations (любой формат) ---
    from arbacc.storage import load_iterations
    records = load_iterations(accel_path / "iterations")
    for r in records:
        # Приводим к единому формату (без _task_meta).
        rec = {k: v for k, v in r.items() if not k.startswith("_")}
        data.iterations.append(rec)

    # --- postprocess ---
    out_root = accel_path.parent.parent.parent.parent
    pp_dir = out_root / "postprocess" / series_id / noise_id / accel_id
    if pp_dir.exists():
        filters_dir = pp_dir / "filters"
        if filters_dir.exists():
            for f_sub in sorted(filters_dir.iterdir()):
                sp = f_sub / "summary.json"
                if sp.exists():
                    try:
                        data.filters[f_sub.name] = json.loads(
                            sp.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError):
                        pass

        env_dir = pp_dir / "envelopes"
        if env_dir.exists():
            for e_sub in sorted(env_dir.iterdir()):
                sp = e_sub / "summary.json"
                if sp.exists():
                    try:
                        summary = json.loads(
                            sp.read_text(encoding="utf-8")
                        )
                        data.envelopes[e_sub.name] = summary
                        env_meta = summary.get("envelope", {}) or {}
                        vals = env_meta.get("envelope_values")
                        if isinstance(vals, list) and vals:
                            data.envelope_values[e_sub.name] = vals
                        up = env_meta.get("envelope_upper")
                        if isinstance(up, list) and up:
                            data.envelope_upper[e_sub.name] = up
                        lo = env_meta.get("envelope_lower")
                        if isinstance(lo, list) and lo:
                            data.envelope_lower[e_sub.name] = lo
                        idxs = env_meta.get("envelope_indices")
                        if isinstance(idxs, list) and idxs:
                            data.envelope_indices[e_sub.name] = idxs
                    except (OSError, json.JSONDecodeError):
                        pass

    return data


# =====================================================================
# Извлечение числовых последовательностей
# =====================================================================

def estimate_floats(data: AccelData) -> tuple[list[int], list[float]]:
    """
    Возвращает x=k и y=float(estimate) для графика траектории.

    Принимает:
        data — задача.

    Возвращает:
        (xs, ys).
    """
    xs: list[int] = []
    ys: list[float] = []
    for rec in data.iterations:
        est = rec.get("estimate")
        if est is None:
            continue
        try:
            ys.append(float(est))
            xs.append(int(rec.get("k", len(xs))))
        except (ValueError, TypeError):
            continue
    return xs, ys

def residual_log10_iterations(
    data: "AccelData",
) -> tuple[list[int], list[float]]:
    """
    Возвращает (xs, log10|diff|) для траектории акселератора.

    Считается ТОЧНО через backend.digits_of — не через float(est - exact).
    Работает для любой dps (30, 100, 300, 3000 — без ограничений).

    log10|diff| = -digits_of(estimate, exact).
    digits_of возвращает целое число верных знаков.

    Принимает:
        data — задача.

    Возвращает:
        (xs, ys), где ys — log10|diff| в виде float (значения
        в диапазоне от -dps до ~0). Пустые списки, если exact_sum
        неизвестен.
    """
    if data.exact_sum is None:
        return [], []

    backend_name = "mpmath"
    dps = 30
    prec = data.input_payload.get("precision")
    if isinstance(prec, dict):
        backend_name = prec.get("backend", "mpmath")
        d = prec.get("dps")
        if isinstance(d, int):
            dps = d

    try:
        from arbacc.precision import get_backend
        from arbacc.core.context import Context
        ctx = Context(backend=get_backend(backend_name), dps=dps)
        exact = ctx.backend.from_str(str(data.exact_sum), dps)
    except Exception:
        return [], []

    xs: list[int] = []
    ys: list[float] = []
    for rec in data.iterations:
        est_str = rec.get("estimate")
        if est_str is None:
            continue
        try:
            est = ctx.backend.from_str(est_str, dps)
            digits = ctx.backend.digits_of(est, exact, dps)
        except Exception:
            continue
        xs.append(int(rec.get("k", len(xs))))
        ys.append(-float(digits))
    return xs, ys


def residual_log10_raw(raw: dict, dps: int, backend_name: str) -> tuple[list[int], list[float]]:
    """
    То же самое для сырой series ({xs, ys, exact_sum}).
    xs — шаги, ys — значения partial sums (строки/числа).
    """
    exact_str = raw.get("exact_sum")
    if not exact_str:
        return [], []
    try:
        from arbacc.precision import get_backend
        from arbacc.core.context import Context
        ctx = Context(backend=get_backend(backend_name), dps=dps)
        exact = ctx.backend.from_str(str(exact_str), dps)
    except Exception:
        return [], []

    xs_in = raw.get("xs", [])
    ys_in = raw.get("ys", [])
    xs_out, ys_out = [], []
    for k, v in zip(xs_in, ys_in):
        try:
            est = ctx.number(v)
            digits = ctx.backend.digits_of(est, exact, dps)
        except Exception:
            continue
        xs_out.append(int(k))
        ys_out.append(-float(digits))
    return xs_out, ys_out


def raw_partial_sums(task: dict, max_n: int = 500) -> tuple[list[int], list[str]]:
    """
    Считает частичные суммы сырого ряда (без акселератора).

    Возвращает (xs, ys_str), где ys_str — СПИСКИ СТРОК полной
    точности. Раньше здесь делался float(...) — это ограничивало
    точность 15-16 знаками и ломало residual на больших dps.
    """
    from arbacc.core.context import Context
    from arbacc.core.stream import partial_value
    from arbacc.core.registry import get as _get
    from arbacc.precision import get_backend

    try:
        backend = get_backend(task["precision"]["backend"])
        dps = int(task["precision"]["dps"])
        ctx = Context(backend=backend, dps=dps)

        SeriesCls = _get("series", task["series"]["type"])
        series_params = task["series"].get("params", {})
        exact_sum_str = (
            task["series"].get("exact_sum")
            or task["series"].get("params", {}).get("exact_sum")
        )
        series = SeriesCls(params=series_params, exact_sum=exact_sum_str)
        source = series.build_stream(ctx)

        noise_spec = task.get("noise")
        if noise_spec and noise_spec.get("type") != "none":
            NoiseCls = _get("noise", noise_spec["type"])
            noise_params = noise_spec.get("params", {})
            seed = int(noise_spec.get("seed", 0))
            noise = NoiseCls(params=noise_params, seed=seed)
            stream = noise.wrap(source, ctx)
        else:
            stream = source

        xs: list[int] = []
        ys_str: list[str] = []
        total = ctx.number(0)
        n_max = min(
            max_n,
            int(task["accelerator"].get("n_max", max_n)
                if task.get("accelerator") else max_n),
        )
        for n in range(n_max):
            try:
                value = partial_value(stream,n,total if n else None,ctx)
            except (IndexError, StopIteration):
                break
            total = value
            xs.append(n + 1)
            ys_str.append(backend.to_str(total, ctx.dps))
        return xs, ys_str
    except Exception:
        return [], []


def build_raw_preview(
    config: dict,
    max_n: int | None = None,
) -> list[dict]:
    """
    Строит список «сырых» partial sums из series × noise × precision.

    Возвращает:
        список {"label", "xs", "ys" (строки полной точности),
                "exact_sum", "backend", "dps"}.

    Значения ys хранятся строками, чтобы residual-вкладка могла
    считать точность на любой dps (не только до 16 знаков).
    """
    from arbacc.runner.expand import expand_all
    from arbacc.runner.scope import matches
    from arbacc.runner.id import node_id

    precisions = expand_all([config.get("precision", {})])
    series_list = expand_all(config.get("series", []))
    noise_list = expand_all(config.get("noise", []))
    if not noise_list:
        noise_list = [{"type": "none", "params": {}, "seed": 0}]

    out: list[dict] = []
    for prec in precisions:
        for series in series_list:
            sid = node_id("series", series["type"], series.get("params", {}))
            for noise in noise_list:
                if not matches(noise.get("applies_to"), {"series": sid}):
                    continue
                nid = node_id(
                    "noise", noise["type"], noise.get("params", {}),
                    extra={"seed": noise.get("seed")},
                )
                resolved_exact = _resolve_exact_sum(
                    series["type"],
                    series.get("params", {}),
                    prec,
                )
                task = {
                    "precision": prec,
                    "series": {
                        "id": sid,
                        "type": series["type"],
                        "params": series.get("params", {}),
                        "exact_sum": resolved_exact,
                    },
                    "noise": {
                        "id": nid,
                        "type": noise["type"],
                        "params": noise.get("params", {}),
                        "seed": noise.get("seed", 0),
                    },
                    "accelerator": {
                        "n_max": max_n if max_n is not None
                                 else int(series.get("params", {}).get("n_raw", 100))
                    },
                }
                xs, ys_str = raw_partial_sums(
                    task, max_n=task["accelerator"]["n_max"]
                )
                if not xs:
                    continue

                d = prec.get("dps") if isinstance(prec, dict) else None
                b = prec.get("backend") if isinstance(prec, dict) else None
                node_for_label = {
                    "type": series["type"],
                    "params": series.get("params", {}),
                }
                label = node_display_short("series", node_for_label)
                if d is not None:
                    label = f"{label} [dps={d}]"
                if nid != "none":
                    noise_node = {
                        "type": noise["type"],
                        "params": noise.get("params", {}),
                    }
                    label = f"{label} / {node_display_short('noise', noise_node)}"

                out.append({
                    "label": label,
                    "xs": xs,
                    "ys": ys_str,           # ← строки, не floats
                    "exact_sum": resolved_exact,
                    "backend": b or "mpmath",
                    "dps": d or 30,
                })
    return out

# =====================================================================
# Загрузка значений фильтров
# =====================================================================

def load_filter_values(
    output_root: Path,
    series_id: str,
    noise_id: str,
    accel_id: str,
    filter_name: str,
) -> tuple[list[int], list[float]]:
    """Читает values фильтра из postprocess (любой формат)."""
    base = (
        output_root / "postprocess"
        / series_id / noise_id / accel_id
        / "filters" / filter_name
    )
    from arbacc.storage import load_values
    records = load_values(base / "values")
    xs: list[int] = []
    ys: list[float] = []
    for rec in records:
        k = rec.get("k")
        v = rec.get("value")
        if k is None or v is None:
            continue
        try:
            ys.append(float(v))
            xs.append(int(k))
        except (ValueError, TypeError):
            continue
    return xs, ys