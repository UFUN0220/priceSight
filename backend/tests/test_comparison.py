"""Cross-platform comparison tests over isolated synthetic source fixtures."""

from pathlib import Path
from decimal import Decimal

from app.cache.offer import OfferCache
from app.comparison.engine import ComparisonEngine
from app.observation.models import Observation
from app.platform.fixture import FixtureOfferAdapter


FIXTURES = Path("backend/tests/fixtures/platform/comparison")


def load_fixture(name: str) -> Observation:
    return Observation.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


def sources() -> list[tuple[FixtureOfferAdapter, Observation]]:
    return [
        (
            FixtureOfferAdapter("fixture-store-a", "com.pricesight.fixture.storea"),
            load_fixture("store_a.json"),
        ),
        (
            FixtureOfferAdapter("fixture-store-b", "com.pricesight.fixture.storeb"),
            load_fixture("store_b.json"),
        ),
    ]


def test_comparison_matches_different_names_and_calculates_final_price() -> None:
    result = ComparisonEngine().compare("可口可乐 500ml×2瓶", sources())

    assert result.comparable is True
    assert result.recommended_platform == "fixture-store-a"
    assert len([offer for offer in result.offers if offer.comparable]) == 2
    store_a = next(offer for offer in result.offers if offer.platform_id == "fixture-store-a")
    store_b = next(offer for offer in result.offers if offer.platform_id == "fixture-store-b")
    assert store_a.final_price.amount == Decimal("10.90")
    assert store_b.final_price.amount == Decimal("11.80")


def test_comparison_does_not_force_mismatched_specifications() -> None:
    result = ComparisonEngine().compare(
        "可口可乐 500ml×2瓶",
        [*sources()[:1], (FixtureOfferAdapter("fixture-store-c", "com.pricesight.fixture.storec"), load_fixture("store_mismatch.json"))],
    )

    assert result.comparable is False
    assert result.recommended_platform is None
    assert "fewer than two" in result.reason
    mismatch = next(offer for offer in result.offers if offer.platform_id == "fixture-store-c")
    assert mismatch.comparable is False
    assert "differ" in (mismatch.match_reason or "")


def test_offer_cache_key_contains_platform_store_product_and_specification() -> None:
    cache = OfferCache(ttl_seconds=10)
    first = cache.key(platform="a", store="store-a", product="cola", specification="500mlx2")
    different_store = cache.key(platform="a", store="store-b", product="cola", specification="500mlx2")
    different_spec = cache.key(platform="a", store="store-a", product="cola", specification="330mlx6")

    assert first != different_store
    assert first != different_spec


def test_second_comparison_uses_cached_normalized_offers() -> None:
    engine = ComparisonEngine(cache=OfferCache(ttl_seconds=10))

    first = engine.compare("可口可乐 500ml×2瓶", sources())
    second = engine.compare("可口可乐 500ml×2瓶", sources())

    assert first.cache_hits == 0
    assert second.cache_hits == 2
