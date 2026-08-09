"""Run and persist the repeatable safe-mode mock-shopping E2E scenario."""

from pathlib import Path

from app.platform.mock_e2e import run_mock_e2e


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evaluation" / "reports" / "phase8_mock_e2e.json"


def main() -> None:
    result = run_mock_e2e()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(result.model_dump_json(indent=2))
    if not result.task_success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
