"""Generic browser-backed platform adapter.

Real platforms should provide their own WebSelectorConfig and subclass or
compose this adapter. No platform-specific selector is placed in BrowserRuntime.
"""

from __future__ import annotations

from app.action.models import ActionTarget
from app.observation.models import Observation, PageType
from app.parser.price import PriceParser
from app.parser.product import ProductParser
from app.parser.specification import PromotionParser
from app.platform.models import (
    AdapterActionDecision,
    AdapterExtraction,
    PlatformPageType,
    PlatformProduct,
)
from app.platform.base import BasePlatformAdapter
from app.platform.web.models import WebSelectorConfig


class WebPlatformAdapter(BasePlatformAdapter):
    """Extract offers from normalized browser observations using configuration."""

    package_name: str | None = None

    def __init__(
        self,
        platform_id: str,
        *,
        selector_config: WebSelectorConfig | None = None,
        allowed_hosts: set[str] | None = None,
    ) -> None:
        self.platform_id = platform_id
        self.selector_config = selector_config or WebSelectorConfig()
        self.allowed_hosts = allowed_hosts or set()
        self.product_parser = ProductParser()
        self.price_parser = PriceParser()
        self.promotion_parser = PromotionParser()

    def identify_platform(self, observation: Observation) -> bool:
        host = observation.package_name
        if not host:
            return False
        if self.allowed_hosts and host not in self.allowed_hosts:
            return False
        return observation.platform == self.platform_id or not self.allowed_hosts

    def identify_page(self, observation: Observation) -> PlatformPageType:
        if not self.identify_platform(observation):
            return PlatformPageType.UNKNOWN
        text = self._text(observation)
        if observation.page_type is PageType.SEARCH:
            return PlatformPageType.SEARCH
        if observation.page_type is PageType.PRODUCT:
            return PlatformPageType.PRODUCT
        if observation.page_type is PageType.CART:
            if any(term in text for term in ("订单确认", "提交订单", "支付")):
                return PlatformPageType.ORDER_CONFIRM
            return PlatformPageType.CART
        if self._product_nodes(observation):
            return PlatformPageType.RESULTS
        if any(term in text for term in ("订单确认", "提交订单")):
            return PlatformPageType.ORDER_CONFIRM
        return PlatformPageType.UNKNOWN

    def extract_products(self, observation: Observation) -> AdapterExtraction:
        page = self.identify_page(observation)
        if page is not PlatformPageType.RESULTS:
            return self._failure(page, "current observation is not a web product list")
        products: list[PlatformProduct] = []
        for node in self._product_nodes(observation):
            if not node.text:
                continue
            parsed = self.product_parser.parse(node.text)
            products.append(
                PlatformProduct(
                    node_id=node.node_id,
                    raw_title=node.text,
                    identity=parsed.product_identity,
                    specification=parsed.specification,
                    price=self.price_parser.parse(node.text),
                    promotions=parsed.promotions,
                )
            )
        if not products:
            return self._failure(page, "web product list contains no parseable cards")
        return AdapterExtraction(
            recognized=True,
            platform_id=self.platform_id,
            page_type=page,
            products=products,
            selector_candidates=self._selector_map(observation),
        )

    def extract_product(self, observation: Observation) -> AdapterExtraction:
        page = self.identify_page(observation)
        if page is not PlatformPageType.PRODUCT:
            return self._failure(page, "current observation is not a web product detail")
        title_node = self._node_by_resource(observation, self.selector_config.product_title_resource_id)
        if title_node is None or not title_node.text:
            return self._failure(page, "web product title selector not found")
        text = self._text(observation)
        parsed = self.product_parser.parse(title_node.text)
        product = PlatformProduct(
            node_id=title_node.node_id,
            raw_title=title_node.text,
            identity=parsed.product_identity,
            specification=parsed.specification,
            price=self.price_parser.parse(text),
            promotions=self.promotion_parser.parse(text),
        )
        return AdapterExtraction(
            recognized=True,
            platform_id=self.platform_id,
            page_type=page,
            product=product,
            price=product.price,
            promotions=product.promotions,
            selector_candidates=self._selector_map(observation),
        )

    def extract_price_promotions(self, observation: Observation) -> AdapterExtraction:
        page = self.identify_page(observation)
        if page is PlatformPageType.UNKNOWN:
            return self._failure(page, "web platform or page was not recognized")
        text = self._text(observation)
        return AdapterExtraction(
            recognized=True,
            platform_id=self.platform_id,
            page_type=page,
            price=self.price_parser.parse(text),
            promotions=self.promotion_parser.parse(text),
            selector_candidates=self._selector_map(observation),
        )

    def selector_candidates(self, observation: Observation, role: str) -> list[ActionTarget]:
        return self._selector_map(observation).get(role, [])

    def build_platform_hints(self, observation: Observation) -> dict[str, list[str]]:
        return {
            "platform": [self.platform_id, observation.package_name or ""],
            "page": [self.identify_page(observation).value],
            "roles": sorted(self._selector_map(observation)),
        }

    def add_to_cart_decision(
        self,
        observation: Observation,
        *,
        safe_mode: bool,
        allow_cart: bool,
    ) -> AdapterActionDecision:
        if safe_mode and not allow_cart:
            return AdapterActionDecision(
                allowed=False,
                safety_stop=True,
                failure_reason="cart action requires explicit SAFE_MODE_ALLOW_CART=true",
            )
        candidate = self.selector_candidates(observation, "add_to_cart")
        if not candidate:
            return AdapterActionDecision(allowed=False, failure_reason="add-to-cart selector not found")
        return AdapterActionDecision(allowed=True, target=candidate[0])

    def _product_nodes(self, observation: Observation):
        prefix = self.selector_config.product_result_resource_prefix
        content_description = self.selector_config.product_result_content_description
        return [
            node
            for node in observation.nodes
            if node.text
            and (
                (node.resource_id and node.resource_id.startswith(prefix))
                or node.content_description == content_description
            )
        ]

    def _selector_map(self, observation: Observation) -> dict[str, list[ActionTarget]]:
        config = self.selector_config
        resource_roles = {
            config.search_resource_id: "search",
            config.search_input_resource_id: "search_input",
            config.search_submit_resource_id: "search_submit",
            config.product_title_resource_id: "product_title",
            config.price_resource_id: "price",
            config.promotion_resource_id: "promotion",
            config.checkout_resource_id: "checkout",
            config.add_to_cart_resource_id: "add_to_cart",
        }
        roles: dict[str, list[ActionTarget]] = {}
        for node in observation.nodes:
            role = resource_roles.get(node.resource_id or "")
            if role is None and node.content_description == config.product_result_content_description:
                role = "product_result"
            if role is None:
                continue
            roles.setdefault(role, []).append(
                ActionTarget(
                    node_id=node.node_id,
                    resource_id=node.resource_id,
                    text=node.text,
                    content_description=node.content_description,
                )
            )
        return roles

    @staticmethod
    def _node_by_resource(observation: Observation, resource_id: str):
        return next((node for node in observation.nodes if node.resource_id == resource_id), None)

    @staticmethod
    def _text(observation: Observation) -> str:
        return " ".join(
            value
            for node in observation.nodes
            for value in (node.text, node.content_description)
            if value
        )

    def _failure(self, page: PlatformPageType, reason: str) -> AdapterExtraction:
        return AdapterExtraction(
            recognized=False,
            platform_id=self.platform_id,
            page_type=page,
            failure_reason=reason,
        )
