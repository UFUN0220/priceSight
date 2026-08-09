"""Run the reproducible local Python quality gate."""

from __future__ import annotations

import subprocess
import sys


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True)


def main() -> int:
    run("-m", "ruff", "check", "backend/app", "backend/tests", "scripts")
    run("-m", "mypy", "backend/app", "--show-error-codes")
    run("-m", "compileall", "-q", "backend/app", "backend/tests", "evaluation", "scripts")
    run("-m", "pre_commit", "run", "--all-files")
    run("-m", "coverage", "run", "--branch", "-m", "pytest", "-q")
    run("-m", "coverage", "report", "--fail-under=80")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
