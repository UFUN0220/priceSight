"""Taobao browser adapter built on the generic web adapter."""

from __future__ import annotations

from urllib.parse import urlparse

from app.observation.models import Observation, ObservationNode, PageType
from app.parser.price import Price
from app.platform.models import AdapterExtraction, PlatformPageType, PlatformProduct
from app.platform.taobao.models import (
    TAOBAO_ALLOWED_HOSTS,
    TaobaoSearchFixture,
    TaobaoStructuredPageFixture,
    TaobaoSelectorConfig,
)
from app.platform.web.adapter import WebPlatformAdapter


class TaobaoPlatformAdapter(WebPlatformAdapter):
    """Taobao-specific boundary with an explicit host allowlist.

    This adapter is fixture-ready. Live selector values remain unverified
    until a public Taobao observation can be captured and reviewed.
    """

    def __init__(
        self,
        *,
        allowed_hosts: set[str] | None = None,
        selector_config: TaobaoSelectorConfig | None = None,
    ) -> None:
        super().__init__(
            "taobao",
            selector_config=selector_config or TaobaoSelectorConfig(),
            allowed_hosts=allowed_hosts or set(TAOBAO_ALLOWED_HOSTS),
        )

    def extract_search_fixture(self, fixture: TaobaoSearchFixture) -> AdapterExtraction:
        """Replay structured product evidence without pretending it is live DOM."""

        products: list[PlatformProduct] = []
        for item in fixture.product_list:
            parsed = self.product_parser.parse(item.title)
            products.append(
                PlatformProduct(
                    node_id=f"taobao-fixture-product-{item.id}",
                    raw_title=item.title,
                    identity=parsed.product_identity,
                    specification=parsed.specification,
                    price=Price(
                        amount=item.price,
                        currency="CNY",
                        original_text=f"¥{item.price:.2f}",
                    ),
                    promotions=parsed.promotions,
                )
            )
        if not products:
            return AdapterExtraction(
                recognized=False,
                platform_id=self.platform_id,
                page_type=PlatformPageType.SEARCH,
                failure_reason="Taobao search fixture contains no products",
            )
        return AdapterExtraction(
            recognized=True,
            platform_id=self.platform_id,
            page_type=PlatformPageType.RESULTS,
            products=products,
        )

    def extract_structured_page_fixture(
        self,
        fixture: TaobaoStructuredPageFixture,
    ) -> AdapterExtraction:
        """Replay the user's sanitized page-structure payload."""

        flat_fixture = TaobaoSearchFixture(
            source_url=fixture.metadata.source_url,
            title=fixture.metadata.title,
            query=fixture.page_structure.search_bar.search_query,
            extracted_date=fixture.metadata.extracted_date,
            product_list=fixture.page_structure.product_list.items,
        )
        return self.extract_search_fixture(flat_fixture)

    def observation_from_structured_page_fixture(
        self,
        fixture: TaobaoStructuredPageFixture,
    ) -> Observation:
        """Convert reviewed page structure into the normal browser observation."""

        page = fixture.page_structure
        host = urlparse(fixture.metadata.source_url).hostname
        nodes = [
            ObservationNode(
                node_id="taobao-search-input",
                resource_id=self.selector_config.search_input_resource_id,
                content_description="搜索商品",
                text=page.search_bar.search_query,
                editable=True,
                visible=True,
            ),
            ObservationNode(
                node_id="taobao-search-submit",
                resource_id=self.selector_config.search_submit_resource_id,
                text=page.search_bar.search_button_label or "搜索",
                clickable=True,
                visible=True,
            ),
        ]
        for index, tab in enumerate(page.search_bar.search_tabs, start=1):
            nodes.append(
                ObservationNode(
                    node_id=f"taobao-search-tab-{index}",
                    text=tab.label,
                    content_description="已选择" if tab.selected else None,
                    clickable=True,
                    visible=True,
                )
            )
        for item in page.product_list.items:
            details = " ".join([*item.features, *item.abstract])
            card_text = f"{item.title} ¥{item.price:.2f} {details}".strip()
            nodes.append(
                ObservationNode(
                    node_id=f"taobao-product-{item.id}",
                    resource_id=f"{self.selector_config.product_result_resource_prefix}-{item.id}",
                    content_description=self.selector_config.product_result_content_description,
                    text=card_text,
                    clickable=True,
                    visible=True,
                )
            )
        return Observation(
            observation_id=f"taobao-structured-{fixture.metadata.extracted_date}-{page.search_bar.search_query}",
            platform=self.platform_id,
            package_name=host,
            page_type=PageType.UNKNOWN,
            source_url=fixture.metadata.source_url,
            title=fixture.metadata.title,
            metadata={
                "search_query": page.search_bar.search_query,
                "current_page": str(page.product_list.pagination.current_page)
                if page.product_list.pagination
                else "1",
            },
            nodes=nodes,
        )
