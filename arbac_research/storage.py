"""Versioned ZSTD Parquet trace dataset. Requires pyarrow, not arbacc."""
from __future__ import annotations
import json
import os
from pathlib import Path

VERSION = 2
COLUMNS = (
    "task_id", "row_type", "n_used", "k", "value", "base_value", "exact_sum",
    "series_id", "class_id", "noise_id", "method_id", "accel_id", "backend", "dps", "status",
    "failure", "baseline_failure", "reference_failure", "elapsed_ms", "params_json",
    "step_elapsed_ms", "op_add", "op_mul", "op_div", "op_neg",
    "op_special", "op_total", "op_mode", "event_type", "event_message",
)


def _arrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        return pa, pq
    except ImportError as exc:
        raise RuntimeError("Установи pyarrow: python -m pip install pyarrow") from exc


def schema():
    pa, _ = _arrow()
    cols = []
    for name in COLUMNS:
        typ = (pa.int64() if name in ("n_used", "k", "dps", "op_add", "op_mul",
                     "op_div", "op_neg", "op_special", "op_total") else
               pa.float64() if name in ("elapsed_ms", "step_elapsed_ms") else pa.string())
        cols.append((name, typ))
    return pa.schema(cols, metadata={b"arbac_research_version": str(VERSION).encode()})


def write_trace(path: str | Path, rows: list[dict], compression_level: int = 5):
    """Atomic compressed Parquet shard, one or more COMPLETE tasks per shard."""
    pa, pq = _arrow()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("cannot write an empty trace")
    serial = [{k: r.get(k) for k in COLUMNS} for r in rows]
    table = pa.Table.from_pylist(serial, schema=schema())
    tmp = path.with_name(path.name + ".tmp")
    try:
        pq.write_table(table, tmp, compression="zstd", compression_level=compression_level,
                       use_dictionary=True, row_group_size=65536)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def iter_parquet_files(path: str | Path):
    p = Path(path)
    if p.is_file():
        if p.suffix.lower() != ".parquet":
            raise ValueError("Ожидается .parquet")
        return [p]
    if (p / "trace").is_dir():
        return sorted((p / "trace").glob("*.parquet"))
    return sorted(p.rglob("*.parquet"))


def iterate_tasks(path: str | Path, mapping: dict | None = None):
    """Yield task rows with bounded memory for native task-contiguous files.

    Legacy external files can be mapped with canonical->source column names.
    External unsorted data should be converted / sorted by task_id first.
    """
    _, pq = _arrow()
    files = iter_parquet_files(path)
    if not files:
        raise FileNotFoundError(f"нет Parquet файлов в {path}")
    for file in files:
        pf = pq.ParquetFile(file)
        cols = set(pf.schema_arrow.names)
        canonical = set(COLUMNS)
        mapping = mapping or {}
        aliases = {"value":"estimate", "failure":"error", "k":"iteration", "class_id":"class"}
        available = {}
        for n in COLUMNS:
            candidate = mapping.get(n, n)
            if candidate not in cols and n in aliases and n not in mapping:
                candidate = aliases[n]
            if candidate in cols:
                available[n] = candidate
        if not {"task_id", "n_used", "value"}.issubset(available):
            raise ValueError(f"{file.name}: нет task_id/n_used/value; используйте mapping JSON")
        if "row_type" not in available:
            # Old exports contain accelerator traces only.
            pass
        current, records = None, []
        seen = set()
        for batch in pf.iter_batches(batch_size=8192, columns=sorted(set(available.values()))):
            data = batch.to_pylist()
            for raw in data:
                row = {canon: raw.get(src) for canon, src in available.items()}
                tid = str(row["task_id"])
                if current is None:
                    current = tid
                if tid != current:
                    seen.add(current)
                    if tid in seen:
                        raise ValueError(f"{file}: task rows interleaved; sort by task_id first")
                    yield records
                    current, records = tid, []
                if not row.get("row_type"):
                    row["row_type"] = "accel"
                records.append(row)
        if records:
            yield records


def write_summary(path, rows):
    pa, pq = _arrow()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("no summaries")
    tab = pa.Table.from_pylist(rows)
    tmp = path.with_name(path.name + ".tmp")
    try:
        pq.write_table(tab, tmp, compression="zstd", compression_level=5)
        tmp.replace(path)
    finally:
        if tmp.exists(): tmp.unlink()


def load_summary(path):
    _, pq = _arrow()
    return pq.read_table(path).to_pylist()


def inspect(path):
    _, pq = _arrow()
    files = iter_parquet_files(path)
    if not files:
        raise FileNotFoundError(path)
    rows = 0
    schemas = []
    for f in files:
        pf = pq.ParquetFile(f)
        rows += pf.metadata.num_rows
        schemas.append(pf.schema_arrow.names)
    return {"files": len(files), "rows": rows, "columns": schemas[0],
            "total_compressed_mb": round(sum(f.stat().st_size for f in files)/2**20, 3)}
