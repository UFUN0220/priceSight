"""Taobao adapter tests using a synthetic, sanitized observation fixture."""

import json
from pathlib import Path

from app.observation.models import Observation
from app.platform.taobao import (
    TaobaoPlatformAdapter,
    TaobaoSearchFixture,
    TaobaoStructuredPageFixture,
)


FIXTURE = Path(__file__).parent / "fixtures" / "web" / "taobao_search.json"


def load_taobao_fixture() -> Observation:
    return Observation.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_taobao_adapter_extracts_synthetic_search_results() -> None:
    observation = load_taobao_fixture()
    extraction = TaobaoPlatformAdapter().extract_products(observation)

    assert extraction.recognized is True
    assert extraction.platform_id == "taobao"
    assert len(extraction.products) == 2
    assert extraction.products[0].price is not None
    assert str(extraction.products[0].price.amount) == "12.80"
    assert extraction.products[0].promotions


def test_taobao_adapter_rejects_same_platform_label_on_unallowed_host() -> None:
    observation = load_taobao_fixture().model_copy(
        update={"package_name": "evil.example", "source_url": "https://evil.example/search"}
    )

    extraction = TaobaoPlatformAdapter().extract_products(observation)

    assert extraction.recognized is False
    assert extraction.failure_reason == "current observation is not a web product list"


def test_taobao_adapter_keeps_cart_blocked_by_default() -> None:
    observation = load_taobao_fixture()
    decision = TaobaoPlatformAdapter().add_to_cart_decision(
        observation,
        safe_mode=True,
        allow_cart=False,
    )

    assert decision.allowed is False
    assert decision.safety_stop is True


def test_taobao_adapter_replays_user_provided_structured_fixture() -> None:
    fixture_path = Path(__file__).parents[2] / "evaluation" / "fixtures" / "web" / "taobao_iphone17_search.json"
    fixture = TaobaoSearchFixture.model_validate(
        json.loads(fixture_path.read_text(encoding="utf-8"))
    )

    extraction = TaobaoPlatformAdapter().extract_search_fixture(fixture)

    assert extraction.recognized is True
    assert len(extraction.products) == 10
    assert str(extraction.products[2].price.amount) == "5068.0"
    assert extraction.products[0].identity.name.startswith("【淘金币可叠加国家补贴】Apple/苹果 iPhone 17")


def test_taobao_adapter_replays_user_page_structure_fixture() -> None:
    fixture_path = Path(__file__).parents[2] / "evaluation" / "fixtures" / "web" / "taobao_iphone17_page_structure.json"
    fixture = TaobaoStructuredPageFixture.model_validate(
        json.loads(fixture_path.read_text(encoding="utf-8"))
    )

    extraction = TaobaoPlatformAdapter().extract_structured_page_fixture(fixture)

    assert fixture.page_structure.search_bar.search_query == "iphone17"
    assert fixture.page_structure.product_list.pagination is not None
    assert fixture.page_structure.product_list.pagination.has_next is True
    assert extraction.recognized is True
    assert len(extraction.products) == 2


def test_taobao_page_fixture_uses_normal_observation_extraction_path() -> None:
    fixture_path = Path(__file__).parents[2] / "evaluation" / "fixtures" / "web" / "taobao_iphone17_page_structure.json"
    fixture = TaobaoStructuredPageFixture.model_validate_json(
        fixture_path.read_text(encoding="utf-8")
    )
    adapter = TaobaoPlatformAdapter()

    observation = adapter.observation_from_structured_page_fixture(fixture)
    extraction = adapter.extract_products(observation)

    assert observation.package_name == "uland.taobao.com"
    assert extraction.recognized is True
    assert len(extraction.products) == 2
    assert str(extraction.products[0].price.amount) == "5999.00"
    assert {"search_input", "search_submit", "product_result"}.issubset(
        extraction.selector_candidates
    )
