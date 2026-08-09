"""Platform-specific selectors and extraction for the Mock Shopping App only."""

from __future__ import annotations

from app.action.models import ActionTarget
from app.observation.models import Observation, PageType
from app.parser.models import ProductIdentity, ProductSpecification
from app.parser.price import PriceParser
from app.parser.product import ProductParser
from app.parser.specification import PromotionParser
from app.platform.models import (
    AdapterActionDecision,
    AdapterExtraction,
    PlatformPageType,
    PlatformProduct,
)


class MockShoppingAdapter:
    """Offline adapter with graceful failure and safe cart gating."""

    platform_id = "mock-shopping"
    package_name = "com.pricesight.mockshopping"

    def __init__(self) -> None:
        self.product_parser = ProductParser()
        self.price_parser = PriceParser()
        self.promotion_parser = PromotionParser()

    def identify_platform(self, observation: Observation) -> bool:
        return observation.package_name == self.package_name or observation.platform == self.platform_id

    def identify_page(self, observation: Observation) -> PlatformPageType:
        if not self.identify_platform(observation):
            return PlatformPageType.UNKNOWN
        if observation.page_type is PageType.SEARCH:
            return PlatformPageType.SEARCH
        if observation.page_type is PageType.PRODUCT:
            text = self._text(observation)
            if "优惠券" in text or "规格" in text:
                return PlatformPageType.PRODUCT
            return PlatformPageType.PRODUCT
        if observation.page_type is PageType.CART:
            return PlatformPageType.CART
        text = self._text(observation)
        if "商品列表" in text or any(node.resource_id and node.resource_id.startswith("result.") for node in observation.nodes):
            return PlatformPageType.RESULTS
        if "订单确认" in text:
            return PlatformPageType.ORDER_CONFIRM
        if "模拟支付" in text or "支付密码" in text:
            return PlatformPageType.PAYMENT
        if "首页" in text or "搜索商品" in text:
            return PlatformPageType.HOME
        return PlatformPageType.UNKNOWN

    def extract_products(self, observation: Observation) -> AdapterExtraction:
        page = self.identify_page(observation)
        if page is not PlatformPageType.RESULTS:
            return self._failure(page, "current observation is not a recognized product list")
        products: list[PlatformProduct] = []
        for node in observation.nodes:
            if not node.text or not node.clickable:
                continue
            if not (node.node_id.startswith("result.") or node.content_description in {"product_result", "product_result_duplicate"}):
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
            return self._failure(page, "recognized product list has no usable product nodes")
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
            return self._failure(page, "current observation is not a product detail page")
        title_node = next(
            (node for node in observation.nodes if node.node_id == "detail.title" and node.text),
            None,
        )
        if title_node is None or title_node.text is None:
            return self._failure(page, "product detail title selector not found")
        parsed = self.product_parser.parse(title_node.text)
        product = PlatformProduct(
            node_id=title_node.node_id,
            raw_title=title_node.text,
            identity=parsed.product_identity,
            specification=parsed.specification,
            price=self.price_parser.parse(self._text(observation)),
            promotions=self.promotion_parser.parse(self._text(observation)),
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
            return self._failure(page, "platform or page was not recognized")
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
            "platform": [self.platform_id, self.package_name],
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
        candidates = self.selector_candidates(observation, "add_to_cart")
        if not candidates:
            return AdapterActionDecision(allowed=False, failure_reason="add_to_cart selector not found")
        return AdapterActionDecision(allowed=True, target=candidates[0])

    def _selector_map(self, observation: Observation) -> dict[str, list[ActionTarget]]:
        roles: dict[str, list[ActionTarget]] = {}
        for node in observation.nodes:
            role = self._role(node.node_id, node.content_description)
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
    def _role(node_id: str, content_description: str | None) -> str | None:
        if node_id == "home.search" or content_description == "search":
            return "search"
        if node_id == "search.input" or content_description == "search_input":
            return "search_input"
        if node_id == "search.submit" or content_description == "search_submit":
            return "search_submit"
        if node_id.startswith("result.") or content_description in {"product_result", "product_result_duplicate"}:
            return "product_result"
        if node_id == "detail.spec_selector" or content_description == "spec_selector":
            return "spec_selector"
        if node_id == "detail.coupon" or content_description == "coupon":
            return "coupon"
        if node_id == "detail.add_to_cart" or content_description == "add_to_cart":
            return "add_to_cart"
        if node_id == "coupon.claim" or content_description == "coupon_claim":
            return "coupon_claim"
        if node_id == "cart.checkout" or content_description == "checkout":
            return "checkout"
        return None

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
