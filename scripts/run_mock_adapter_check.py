"""Run offline adapter success/failure cases without a device or network."""

import json
from pathlib import Path

from app.observation.models import Observation
from app.platform.mock import MockShoppingAdapter


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "backend" / "tests" / "fixtures" / "platform" / "mock"
REPORT = ROOT / "evaluation" / "reports" / "phase9_mock_adapter.json"


def main() -> None:
    adapter = MockShoppingAdapter()
    results = Observation.model_validate_json((FIXTURES / "results.json").read_text(encoding="utf-8"))
    detail = Observation.model_validate_json((FIXTURES / "detail.json").read_text(encoding="utf-8"))
    unknown = Observation(observation_id="unknown", platform="other", package_name="com.other.app")
    success = adapter.extract_products(results)
    detail_result = adapter.extract_product(detail)
    failure = adapter.extract_products(unknown)
    report = {
        "adapter": adapter.platform_id,
        "mode": "offline_mock_only",
        "physical_device_connected": False,
        "success_case": {
            "recognized": success.recognized,
            "product_count": len(success.products),
            "page_type": success.page_type.value,
        },
        "detail_case": {
            "recognized": detail_result.recognized,
            "price": str(detail_result.price.amount) if detail_result.price else None,
        },
        "graceful_failure_case": {
            "recognized": failure.recognized,
            "reason": failure.failure_reason,
        },
        "real_platform_result": "not attempted by explicit user instruction: no physical device",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
