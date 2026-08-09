"""Taobao adapter tests using a synthetic, sanitized observation fixture."""

import json
from pathlib import Path

import pytest

from app.observation.models import Observation, ObservationNode, PageType
from app.platform.taobao import (
    TaobaoPlatformAdapter,
    TaobaoPageState,
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
    assert extraction.failure_reason == "Taobao page state is UNKNOWN: host or platform identity is not allowed"


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


def make_page(
    *,
    text: str,
    source_url: str = "https://s.taobao.com/search",
    page_type: PageType = PageType.SEARCH,
    nodes: list[ObservationNode] | None = None,
) -> Observation:
    return Observation(
        observation_id="taobao-state-test",
        platform="taobao",
        package_name="s.taobao.com",
        page_type=page_type,
        source_url=source_url,
        title=text,
        nodes=nodes
        or [
            ObservationNode(
                node_id="state-text",
                text=text,
                visible=True,
            )
        ],
    )


def test_taobao_page_states_cover_loading_login_popup_empty_and_unknown() -> None:
    adapter = TaobaoPlatformAdapter()
    cases = [
        (make_page(text="加载中，请稍候"), TaobaoPageState.LOADING),
        (
            make_page(
                text="请先登录",
                nodes=[ObservationNode(node_id="login", role="dialog", text="请先登录")],
            ),
            TaobaoPageState.LOGIN_REQUIRED,
        ),
        (
            make_page(
                text="提示",
                nodes=[ObservationNode(node_id="popup", role="dialog", text="提示")],
            ),
            TaobaoPageState.POPUP,
        ),
        (make_page(text="暂无商品"), TaobaoPageState.EMPTY_RESULT),
        (
            make_page(text="欢迎来到淘宝", source_url="https://www.taobao.com/", page_type=PageType.UNKNOWN),
            TaobaoPageState.UNKNOWN,
        ),
    ]

    for observation, expected in cases:
        assert adapter.assess_page(observation).state is expected


def test_taobao_page_state_distinguishes_search_result_and_product_list() -> None:
    adapter = TaobaoPlatformAdapter()
    product = ObservationNode(
        node_id="product-1",
        class_name="div",
        text="iPhone 17 ¥5999",
        href="https://item.taobao.com/item.htm?id=123",
        clickable=True,
        visible=True,
    )

    search = make_page(text="搜索结果", nodes=[product, ObservationNode(node_id="input", editable=True)])
    listing = make_page(
        text="商品列表",
        source_url="https://www.taobao.com/list",
        page_type=PageType.UNKNOWN,
        nodes=[product],
    )

    assert adapter.assess_page(search).state is TaobaoPageState.SEARCH_RESULT
    assert adapter.assess_page(listing).state is TaobaoPageState.PRODUCT_LIST


def test_taobao_selector_fallback_records_href_strategy_and_product_evidence() -> None:
    observation = make_page(
        text="商品列表",
        source_url="https://s.taobao.com/search",
        nodes=[
            ObservationNode(
                node_id="product-href",
                class_name="div",
                text="Apple iPhone 17 ¥5999",
                href="https://item.taobao.com/item.htm?id=123456",
                attributes={"data-seller": "示例店铺", "data-sales": "已售100+"},
                clickable=True,
                visible=True,
            )
        ],
    )
    extraction = TaobaoPlatformAdapter().extract_products(observation)

    assert extraction.recognized is True
    assert extraction.selector_strategy["product_result"] == "href_product_id"
    assert extraction.selector_fallback_level["product_result"] == 3
    product = extraction.products[0]
    assert product.product_id == "123456"
    assert product.product_url == "https://item.taobao.com/item.htm?id=123456"
    assert product.seller == "示例店铺"
    assert product.sales_info == "已售100+"
    assert product.observation_id == observation.observation_id
    assert product.extraction_source == "browser_observation"


def test_taobao_missing_price_is_null_and_missing_title_is_rejected() -> None:
    adapter = TaobaoPlatformAdapter()
    missing_price = make_page(
        text="商品列表",
        nodes=[
            ObservationNode(
                node_id="without-price",
                class_name="div",
                text="Apple iPhone 17",
                href="https://item.taobao.com/item.htm?id=1",
                clickable=True,
            )
        ],
    )
    missing_title = make_page(
        text="商品列表",
        nodes=[
            ObservationNode(
                node_id="without-title",
                class_name="div",
                text="¥10.00",
                href="https://item.taobao.com/item.htm?id=2",
                clickable=True,
            )
        ],
    )

    price_result = adapter.extract_products(missing_price)
    title_result = adapter.extract_products(missing_title)

    assert price_result.recognized is True
    assert price_result.products[0].price is None
    assert title_result.recognized is False
    assert "usable product title" in (title_result.failure_reason or "")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("需要完成验证码", TaobaoPageState.RISK_BLOCKED),
        ("安全验证", TaobaoPageState.RISK_BLOCKED),
    ],
)
def test_taobao_risk_text_stops_before_product_extraction(
    text: str,
    expected: TaobaoPageState,
) -> None:
    adapter = TaobaoPlatformAdapter()
    observation = make_page(
        text=text,
        nodes=[
            ObservationNode(
                node_id="risk",
                text=text,
                visible=True,
            ),
            ObservationNode(
                node_id="product",
                text="Apple iPhone 17 ¥5999",
                content_description="taobao_product_result",
                visible=True,
            ),
        ],
    )

    assert adapter.assess_page(observation).state is expected
    assert adapter.extract_products(observation).recognized is False
