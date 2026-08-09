"""Tests for the offline first platform adapter and safe cart boundary."""

import json
from decimal import Decimal
from pathlib import Path

from app.platform.mock import MockShoppingAdapter
from app.platform.models import PlatformPageType
from app.observation.models import Observation


FIXTURES = Path("backend/tests/fixtures/platform/mock")


def load_fixture(name: str) -> Observation:
    return Observation.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


def test_mock_adapter_identifies_platform_and_extracts_duplicate_results() -> None:
    adapter = MockShoppingAdapter()
    observation = load_fixture("results.json")

    assert adapter.identify_platform(observation) is True
    assert adapter.identify_page(observation) is PlatformPageType.RESULTS
    result = adapter.extract_products(observation)

    assert result.recognized is True
    assert len(result.products) == 3
    assert result.products[0].identity.name == "可口可乐"
    assert result.products[0].specification.primary_quantity is not None
    assert result.products[0].specification.primary_quantity.count == 2
    assert len(adapter.selector_candidates(observation, "product_result")) == 3


def test_mock_adapter_extracts_detail_price_promotions_and_multiple_selectors() -> None:
    adapter = MockShoppingAdapter()
    observation = load_fixture("detail.json")

    result = adapter.extract_product(observation)
    price_result = adapter.extract_price_promotions(observation)

    assert result.recognized is True
    assert result.product is not None
    assert result.price is not None and result.price.amount == Decimal("12.90")
    assert price_result.price is not None and price_result.price.amount == Decimal("12.90")
    assert len(price_result.promotions) == 1
    assert len(adapter.selector_candidates(observation, "coupon")) == 1
    assert len(adapter.selector_candidates(observation, "add_to_cart")) == 1


def test_mock_adapter_fails_gracefully_for_unknown_or_missing_selectors() -> None:
    adapter = MockShoppingAdapter()
    unknown = Observation(
        observation_id="other",
        platform="other-app",
        package_name="com.other.app",
        nodes=[],
    )

    result = adapter.extract_products(unknown)
    cart = adapter.add_to_cart_decision(unknown, safe_mode=False, allow_cart=True)

    assert adapter.identify_platform(unknown) is False
    assert result.recognized is False
    assert result.failure_reason is not None
    assert cart.allowed is False
    assert "selector" in (cart.failure_reason or "")


def test_cart_is_blocked_by_default_and_only_allowed_explicitly() -> None:
    adapter = MockShoppingAdapter()
    observation = load_fixture("detail.json")

    blocked = adapter.add_to_cart_decision(observation, safe_mode=True, allow_cart=False)
    allowed = adapter.add_to_cart_decision(observation, safe_mode=True, allow_cart=True)

    assert blocked.allowed is False
    assert blocked.safety_stop is True
    assert allowed.allowed is True
    assert allowed.target is not None
