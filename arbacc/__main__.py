"""
Точка входа CLI: `python3 -m arbacc --config test.json`.

Зачем:
    Позволяет запускать ядро одной командой без явного указания
    подкоманды. Если первым аргументом идёт `--config` (или просто
    путь к JSON), это эквивалентно `run`.

    Полные подкоманды (validate, plan, run) остаются доступны через
    arbacc.cli.

Как расширять:
    Если понадобится больше сокращений — добавь сюда обработку.

Примеры:
    python3 -m arbacc --config test.json
    python3 -m arbacc --config test.json --output out/my_run
    python3 -m arbacc run test.json               # явная подкоманда
    python3 -m arbacc validate test.json
    python3 -m arbacc plan test.json
"""

from __future__ import annotations
import sys
from pathlib import Path

from arbacc.cli import main as cli_main


def main() -> int:
    """
    Разбирает argv и решает, что вызвать.

    Если первый аргумент — `--config <path>`, `--config=<path>`,
    или просто путь к существующему .json, вызываем `run`.
    Иначе передаём в cli_main как есть.
    """
    argv = sys.argv[1:]

    # Случай 1: --config <path>
    if "--config" in argv:
        idx = argv.index("--config")
        if idx + 1 >= len(argv):
            print("error: --config requires a path", file=sys.stderr)
            return 2
        config_path = argv[idx + 1]
        # Убираем --config <path> из argv, чтобы cli_main не спотыкался.
        rest = argv[:idx] + argv[idx + 2:]
        # Собираем новый argv: run <config> <rest...>
        sys.argv = [sys.argv[0], "run", config_path] + rest
        return cli_main()

    # Случай 2: --config=<path>
    for i, a in enumerate(argv):
        if a.startswith("--config="):
            config_path = a.split("=", 1)[1]
            rest = argv[:i] + argv[i + 1:]
            sys.argv = [sys.argv[0], "run", config_path] + rest
            return cli_main()

    # Случай 3: первый аргумент — путь к .json
    if argv and not argv[0].startswith("-") and argv[0].endswith(".json"):
        config_path = argv[0]
        rest = argv[1:]
        sys.argv = [sys.argv[0], "run", config_path] + rest
        return cli_main()

    # Иначе — обычный cli_main.
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())