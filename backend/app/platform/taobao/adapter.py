"""Taobao browser adapter built on the generic web adapter."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.action.models import ActionTarget
from app.observation.models import Observation, ObservationNode, PageType
from app.parser.price import Price
from app.platform.models import AdapterExtraction, PlatformPageType, PlatformProduct
from app.platform.taobao.models import (
    TAOBAO_ALLOWED_HOSTS,
    TaobaoPageAssessment,
    TaobaoPageState,
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

    def assess_page(self, observation: Observation) -> TaobaoPageAssessment:
        """Classify a Taobao observation without guessing from URL alone."""

        host_verified = self.identify_platform(observation)
        if not host_verified:
            return TaobaoPageAssessment(
                state=TaobaoPageState.UNKNOWN,
                reason="host or platform identity is not allowed",
                host_verified=False,
            )
        text = self._observation_text(observation)
        if self._contains_risk_block(text):
            return TaobaoPageAssessment(
                state=TaobaoPageState.RISK_BLOCKED,
                reason="captcha or security verification text detected",
                host_verified=True,
            )
        if self._contains_blocking_login(text, observation):
            return TaobaoPageAssessment(
                state=TaobaoPageState.LOGIN_REQUIRED,
                reason="blocking login state detected",
                host_verified=True,
            )
        if self._contains_popup(observation):
            return TaobaoPageAssessment(
                state=TaobaoPageState.POPUP,
                reason="visible dialog or modal detected",
                host_verified=True,
            )
        if self._contains_loading(text, observation):
            return TaobaoPageAssessment(
                state=TaobaoPageState.LOADING,
                reason="page reports an unfinished loading state",
                host_verified=True,
            )

        product_nodes = self._product_nodes_with_evidence(observation)
        if product_nodes and self._detail_signal(observation, text):
            return TaobaoPageAssessment(
                state=TaobaoPageState.PRODUCT_DETAIL,
                reason="detail URL or detail semantic structure detected",
                host_verified=True,
            )
        if product_nodes:
            state = (
                TaobaoPageState.SEARCH_RESULT
                if self._search_signal(observation, text)
                else TaobaoPageState.PRODUCT_LIST
            )
            return TaobaoPageAssessment(
                state=state,
                reason="product candidates detected from page structure",
                host_verified=True,
            )
        if self._empty_signal(observation, text):
            return TaobaoPageAssessment(
                state=TaobaoPageState.EMPTY_RESULT,
                reason="search page reports no matching products",
                host_verified=True,
            )
        if self._detail_signal(observation, text):
            return TaobaoPageAssessment(
                state=TaobaoPageState.PRODUCT_DETAIL,
                reason="detail URL or detail semantic structure detected",
                host_verified=True,
            )
        return TaobaoPageAssessment(
            state=TaobaoPageState.UNKNOWN,
            reason="no stable Taobao page structure recognized",
            host_verified=True,
        )

    def identify_page(self, observation: Observation) -> PlatformPageType:
        state = self.assess_page(observation).state
        if state in (TaobaoPageState.SEARCH_RESULT, TaobaoPageState.PRODUCT_LIST):
            return PlatformPageType.RESULTS
        if state is TaobaoPageState.PRODUCT_DETAIL:
            return PlatformPageType.PRODUCT
        if state is TaobaoPageState.EMPTY_RESULT:
            return PlatformPageType.SEARCH
        return PlatformPageType.UNKNOWN

    def extract_products(self, observation: Observation) -> AdapterExtraction:
        assessment = self.assess_page(observation)
        if assessment.state not in (
            TaobaoPageState.SEARCH_RESULT,
            TaobaoPageState.PRODUCT_LIST,
        ):
            return self._failure(
                self.identify_page(observation),
                f"Taobao page state is {assessment.state.value}: {assessment.reason}",
            )

        candidates = self._product_nodes_with_evidence(observation)
        products: list[PlatformProduct] = []
        for node, strategy, fallback_level in candidates:
            if not node.text or self._looks_price_only(node.text):
                continue
            parsed = self.product_parser.parse(node.text)
            displayed_price = self.price_parser.parse(node.text)
            products.append(
                PlatformProduct(
                    node_id=node.node_id,
                    raw_title=node.text,
                    identity=parsed.product_identity,
                    specification=parsed.specification,
                    price=displayed_price,
                    displayed_price=displayed_price,
                    original_price=self._original_price(node),
                    product_url=node.href,
                    product_id=self._product_id(node),
                    seller=self._attribute(node, "data-seller", "data-shop"),
                    sales_info=self._attribute(node, "data-sales"),
                    observation_id=observation.observation_id,
                    extraction_source="browser_observation",
                    selector_strategy=strategy,
                    selector_fallback_level=fallback_level,
                    confidence=max(0.5, 1.0 - 0.1 * (fallback_level - 1)),
                    promotions=parsed.promotions,
                )
            )
        if not products:
            return self._failure(
                PlatformPageType.RESULTS,
                "Taobao product candidates contained no usable product title",
            )

        selector_candidates = super()._selector_map(observation)
        selector_strategy = {"product_result": candidates[0][1]}
        selector_fallback_level = {"product_result": candidates[0][2]}
        product_targets = [self._target(node) for node, _, _ in candidates]
        selector_candidates["product_result"] = product_targets
        for role in ("search_input", "search_submit"):
            action_nodes = self._action_nodes(observation, role)
            if action_nodes:
                nodes, strategy, fallback_level = action_nodes
                selector_candidates[role] = [self._target(node) for node in nodes]
                selector_strategy[role] = strategy
                selector_fallback_level[role] = fallback_level
        return AdapterExtraction(
            recognized=True,
            platform_id=self.platform_id,
            page_type=PlatformPageType.RESULTS,
            products=products,
            selector_candidates=selector_candidates,
            selector_strategy=selector_strategy,
            selector_fallback_level=selector_fallback_level,
        )

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

    def _product_nodes_with_evidence(
        self,
        observation: Observation,
    ) -> list[tuple[ObservationNode, str, int]]:
        config = self.selector_config
        stages = (
            (
                "aria_semantic",
                lambda node: node.content_description == config.product_result_content_description
                or (
                    node.role in {"link", "article"}
                    and self._has_price(node.text)
                ),
            ),
            (
                "stable_attribute",
                lambda node: bool(
                    node.resource_id
                    and node.resource_id.startswith(config.product_result_resource_prefix)
                )
                or bool(self._attribute(node, "data-item-id", "data-id")),
            ),
            (
                "href_product_id",
                lambda node: bool(
                    node.href
                    and ("taobao.com" in node.href or self._product_id(node))
                ),
            ),
            (
                "dom_structure",
                lambda node: node.class_name in {"a", "article", "li"}
                and self._has_price(node.text),
            ),
            (
                "text_assisted",
                lambda node: bool(node.clickable and self._has_price(node.text)),
            ),
        )
        selected: dict[str, tuple[ObservationNode, str, int]] = {}
        for level, (strategy, predicate) in enumerate(stages, start=1):
            for node in observation.nodes:
                if node.node_id not in selected and predicate(node):
                    selected[node.node_id] = (node, strategy, level)
        return list(selected.values())

    def _action_nodes(
        self,
        observation: Observation,
        role: str,
    ) -> tuple[list[ObservationNode], str, int] | None:
        config = self.selector_config
        for level, (strategy, predicate) in enumerate(
            (
                (
                    "aria_semantic",
                    lambda node: (
                        role == "search_input"
                        and node.editable
                        and node.role in {"searchbox", "textbox"}
                    )
                    or (
                        role == "search_submit"
                        and node.role == "button"
                        and (node.text or "搜索")
                    ),
                ),
                (
                    "stable_attribute",
                    lambda node: node.resource_id
                    == (
                        config.search_input_resource_id
                        if role == "search_input"
                        else config.search_submit_resource_id
                    ),
                ),
                (
                    "text_assisted",
                    lambda node: (
                        role == "search_input"
                        and node.editable
                    )
                    or (
                        role == "search_submit"
                        and "搜索" in (node.text or "")
                        and node.clickable
                    ),
                ),
            ),
            start=1,
        ):
            nodes = [node for node in observation.nodes if predicate(node)]
            if nodes:
                return nodes, strategy, level
        return None

    @staticmethod
    def _observation_text(observation: Observation) -> str:
        values = [observation.title or "", observation.source_url or ""]
        values.extend(
            value
            for node in observation.nodes
            for value in (node.text, node.content_description)
            if value
        )
        return " ".join(values).casefold()

    @staticmethod
    def _has_price(text: str | None) -> bool:
        return bool(text and re.search(r"(?:¥|￥|人民币|RMB)\s*\d", text, re.IGNORECASE))

    @staticmethod
    def _looks_price_only(text: str) -> bool:
        remainder = re.sub(r"(?:¥|￥|人民币|RMB)\s*\d+(?:\.\d{1,2})?", "", text, flags=re.IGNORECASE)
        return not remainder.strip(" \t\r\n·|-:")

    @staticmethod
    def _attribute(node: ObservationNode, *names: str) -> str | None:
        for name in names:
            value = node.attributes.get(name)
            if value:
                return value
        return None

    @classmethod
    def _product_id(cls, node: ObservationNode) -> str | None:
        direct = cls._attribute(node, "data-item-id", "data-id")
        if direct:
            return direct
        if node.href:
            match = re.search(r"(?:[?&]id=|/item/)([A-Za-z0-9_-]+)", node.href)
            if match:
                return match.group(1)
        return None

    @classmethod
    def _original_price(cls, node: ObservationNode) -> Price | None:
        value = cls._attribute(node, "data-original-price")
        if not value:
            return None
        match = re.search(r"\d+(?:\.\d{1,2})?", value)
        return Price(amount=match.group(0), original_text=value) if match else None

    @staticmethod
    def _target(node: ObservationNode) -> ActionTarget:
        return ActionTarget(
            node_id=node.node_id,
            resource_id=node.resource_id,
            text=node.text,
            content_description=node.content_description,
            semantic_hint=node.role,
            bounds=node.bounds,
        )

    @staticmethod
    def _contains_risk_block(text: str) -> bool:
        return any(term in text for term in ("验证码", "滑块验证", "安全验证", "风险验证", "captcha"))

    @staticmethod
    def _contains_blocking_login(text: str, observation: Observation) -> bool:
        if any(term in text for term in ("请先登录", "登录后查看", "登录后继续", "账号登录", "扫码登录")):
            return True
        return any(
            node.role in {"dialog", "alertdialog"}
            and "登录" in (node.text or "")
            for node in observation.nodes
        )

    @staticmethod
    def _contains_popup(observation: Observation) -> bool:
        return any(
            node.role in {"dialog", "alertdialog"}
            or (node.class_name or "").lower() in {"dialog", "modal"}
            for node in observation.nodes
        )

    @staticmethod
    def _contains_loading(text: str, observation: Observation) -> bool:
        return observation.metadata.get("loading", "").casefold() == "true" or any(
            term in text for term in ("加载中", "正在加载", "请稍候", "loading")
        )

    def _search_signal(self, observation: Observation, text: str) -> bool:
        return (
            observation.page_type is PageType.SEARCH
            or "/search" in (observation.source_url or "")
            or "tbsearch" in (observation.source_url or "")
            or any(node.editable for node in observation.nodes)
            or "搜索" in text
        )

    def _detail_signal(self, observation: Observation, text: str) -> bool:
        return (
            "/item.htm" in (observation.source_url or "")
            or "/item/" in (observation.source_url or "")
            or "商品详情" in text
            or any(
                node.resource_id == self.selector_config.product_title_resource_id
                for node in observation.nodes
            )
        )

    def _empty_signal(self, observation: Observation, text: str) -> bool:
        return self._search_signal(observation, text) and any(
            term in text for term in ("没有找到", "暂无商品", "无相关商品", "没有相关商品")
        )
