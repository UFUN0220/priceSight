"""Generic browser platform adapter tests using sanitized Mock Web observations."""

from decimal import Decimal

from app.comparison.engine import ComparisonEngine
from app.observation.models import Observation, ObservationNode, PageType
from app.platform.web.adapter import WebPlatformAdapter


def web_results(platform: str, price: str) -> Observation:
    return Observation(
        observation_id=f"{platform}-results",
        platform=platform,
        package_name="127.0.0.1",
        page_type=PageType.UNKNOWN,
        source_url="http://127.0.0.1/results",
        nodes=[
            ObservationNode(
                node_id="browser.node.1",
                resource_id="product-result-1",
                content_description="product_result",
                text=f"可口可乐 500ml 2瓶 ¥{price}",
                clickable=True,
            )
        ],
    )


def test_web_adapter_extracts_product_and_price_from_browser_observation() -> None:
    adapter = WebPlatformAdapter("mock-web", allowed_hosts={"127.0.0.1"})
    extraction = adapter.extract_products(web_results("mock-web", "10.90"))

    assert extraction.recognized is True
    assert extraction.products[0].specification.primary_quantity is not None
    assert extraction.products[0].price is not None
    assert extraction.products[0].price.amount == Decimal("10.90")
    assert adapter.selector_candidates(web_results("mock-web", "10.90"), "product_result")


def test_web_adapter_rejects_unknown_host() -> None:
    adapter = WebPlatformAdapter("other-web", allowed_hosts={"trusted.example"})

    extraction = adapter.extract_products(web_results("mock-web", "10.90"))

    assert extraction.recognized is False
    assert extraction.failure_reason == "current observation is not a web product list"


def test_web_adapter_offers_can_feed_existing_comparison_engine() -> None:
    source_a = WebPlatformAdapter("web-a", allowed_hosts={"127.0.0.1"})
    source_b = WebPlatformAdapter("web-b", allowed_hosts={"127.0.0.1"})

    result = ComparisonEngine().compare(
        "可口可乐 500ml 2瓶",
        [
            (source_a, web_results("web-a", "10.90")),
            (source_b, web_results("web-b", "11.80")),
        ],
    )

    assert result.comparable is True
    assert result.recommended_platform == "web-a"
