"""Phase 5 adapter contract and cross-platform comparison regressions."""

from pathlib import Path

import pytest

from app.comparison.engine import ComparisonEngine
from app.core.safety import SafetyDecision
from app.observation.models import Observation
from app.platform.base import PlatformAdapter
from app.platform.jd import JdPlatformAdapter
from app.platform.meituan import MeituanPlatformAdapter
from app.platform.taobao import TaobaoPlatformAdapter


FIXTURES = Path("backend/tests/fixtures/platform/comparison")


def load_fixture(name: str) -> Observation:
    return Observation.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("adapter", "fixture_name", "source"),
    [
        (JdPlatformAdapter(), "jd.json", "jd_fixture"),
        (MeituanPlatformAdapter(), "meituan.json", "meituan_fixture"),
    ],
)
def test_adapters_implement_unified_contract(adapter, fixture_name: str, source: str) -> None:
    observation = load_fixture(fixture_name)

    assert isinstance(adapter, PlatformAdapter)
    extraction = adapter.parse_products(observation)
    assert extraction.recognized is True
    normalized = adapter.normalize_product(extraction.products[0])
    assert normalized.platform == adapter.platform_id
    assert normalized.title
    assert normalized.quantity is not None
    assert normalized.effective_price is not None
    assert normalized.extraction_source == source


def test_taobao_uses_the_same_normalized_contract() -> None:
    observation = Observation.model_validate_json(
        Path("backend/tests/fixtures/web/taobao_search.json").read_text(encoding="utf-8")
    )
    adapter = TaobaoPlatformAdapter()

    assert isinstance(adapter, PlatformAdapter)
    extraction = adapter.parse_products(observation)
    assert extraction.recognized is True
    normalized = adapter.normalize_product(extraction.products[0])
    assert normalized.platform == "taobao"
    assert normalized.extraction_source == "browser_observation"


def test_cross_platform_comparison_uses_effective_unit_price() -> None:
    result = ComparisonEngine().compare(
        "可口可乐 500ml×2瓶",
        [
            (JdPlatformAdapter(), load_fixture("jd.json")),
            (MeituanPlatformAdapter(), load_fixture("meituan.json")),
        ],
    )

    assert result.comparable is True
    assert result.recommended_platform == "meituan"
    jd = next(offer for offer in result.offers if offer.platform_id == "jd")
    meituan = next(offer for offer in result.offers if offer.platform_id == "meituan")
    assert jd.effective_unit_price is not None
    assert meituan.effective_unit_price is not None
    assert meituan.effective_unit_price < jd.effective_unit_price
    assert jd.extraction_source == "jd_fixture"
    assert meituan.extraction_source == "meituan_fixture"


def test_adapter_safety_boundary_stops_order_confirmation() -> None:
    observation = Observation.model_validate(
        {
            "observation_id": "jd-order-confirm-fixture",
            "platform": "jd",
            "package_name": "com.pricesight.fixture.jd",
            "page_type": "unknown",
            "nodes": [{"node_id": "order", "text": "订单确认 页面"}],
        }
    )

    assert JdPlatformAdapter().safety_boundary(observation) is SafetyDecision.STOP
