"""Run the phase 10 synthetic multi-source comparison without a device or network."""

import json
from pathlib import Path

from app.cache.offer import OfferCache
from app.comparison.engine import ComparisonEngine
from app.observation.models import Observation
from app.platform.fixture import FixtureOfferAdapter


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "backend" / "tests" / "fixtures" / "platform" / "comparison"
REPORT = ROOT / "evaluation" / "reports" / "phase10_offline_comparison.json"


def load(name: str) -> Observation:
    return Observation.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


def main() -> None:
    sources = [
        (FixtureOfferAdapter("fixture-store-a", "com.pricesight.fixture.storea"), load("store_a.json")),
        (FixtureOfferAdapter("fixture-store-b", "com.pricesight.fixture.storeb"), load("store_b.json")),
    ]
    mismatch_sources = [
        *sources[:1],
        (FixtureOfferAdapter("fixture-store-c", "com.pricesight.fixture.storec"), load("store_mismatch.json")),
    ]
    engine = ComparisonEngine(cache=OfferCache(ttl_seconds=300))
    first = engine.compare("可口可乐 500ml×2瓶", sources)
    second = engine.compare("可口可乐 500ml×2瓶", sources)
    mismatch = engine.compare("可口可乐 500ml×2瓶", mismatch_sources)
    report = {
        "mode": "offline_synthetic_only",
        "physical_device_connected": False,
        "real_platforms_supported": [],
        "comparable_case": {
            "comparable": first.comparable,
            "recommended_platform": first.recommended_platform,
            "offers": [
                {
                    "platform": offer.platform_id,
                    "final_price": str(offer.final_price.amount) if offer.final_price.amount else None,
                    "comparable": offer.comparable,
                }
                for offer in first.offers
            ],
        },
        "cache_case": {"first_hits": first.cache_hits, "second_hits": second.cache_hits},
        "mismatch_case": {"comparable": mismatch.comparable, "reason": mismatch.reason},
        "real_platform_note": "Meituan/JD/Taobao were not claimed or contacted; no physical device was connected.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
