"""
Публичный экспорт модулей раннера.

Зачем:
    Чтобы в cli.py и тестах можно было писать
    `from arbacc.runner import build_plan, execute_accel`
    вместо длинных путей.

    Плюс — при импорте runner автоматически импортируются все пакеты
    плагинов, чтобы реестр был заполнен.

Как расширять:
    При добавлении новых модулей раннера — добавь импорт сюда.
    При добавлении новой категории плагинов — добавь её пакет
    в блок «Регистрация плагинов» ниже.
"""

# --- Регистрация плагинов: autodiscovery --------------------------------
# Должно быть ДО импорта build_plan, чтобы реестр был заполнен.
import arbacc.series        # noqa: F401
import arbacc.noise         # noqa: F401
import arbacc.accelerators  # noqa: F401
import arbacc.stopping      # noqa: F401
import arbacc.postprocess   # noqa: F401
import arbacc.envelopes     # noqa: F401


# --- Публичные экспорты -------------------------------------------------
from arbacc.runner.expand import expand_node, expand_all
from arbacc.runner.scope import matches
from arbacc.runner.id import node_id, canonical_json
from arbacc.runner.plan import build_plan
from arbacc.runner.execute import execute_accel, execute_post
from arbacc.runner.skip import (
    should_skip,
    should_skip_post,
    expected_manifest,
    build_input_payload,
)
from arbacc.runner.progress import Progress
from arbacc.runner.errors import ErrorLog
from arbacc.runner.run_accel import run_accelerator
from arbacc.runner.run_postprocess import (
    run_offline_envelopes,
    run_postprocessors,
    save_postprocess_results,
)
from arbacc.runner.save_result import save_accelerated_result
from arbacc.runner.metrics import digits_gained, envelope_was_right

__all__ = [
    # expand
    "expand_node", "expand_all",
    # scope
    "matches",
    # id
    "node_id", "canonical_json",
    # plan
    "build_plan",
    # execute
    "execute_accel", "execute_post",
    # skip
    "should_skip", "should_skip_post", "expected_manifest", "build_input_payload",
    # progress / errors
    "Progress", "ErrorLog",
    # run_accel
    "run_accelerator",
    # run_postprocess
    "run_offline_envelopes", "run_postprocessors",
    "save_postprocess_results",
    # save_result
    "save_accelerated_result",
    # metrics
    "digits_gained", "envelope_was_right",
]