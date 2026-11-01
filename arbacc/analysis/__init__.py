"""Модуль массового анализа output."""
from arbacc.analysis.analyze import (
    analyze, format_table,
)
__all__ = ["analyze", "format_table"]
from arbacc.analysis.experiment import (
    analyze_profiling, build_experiment_matrix, rank_algorithms, export_experiment_report,
)
__all__ += ["analyze_profiling", "build_experiment_matrix", "rank_algorithms", "export_experiment_report"]
