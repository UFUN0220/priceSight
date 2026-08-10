"""Platform adapter contract and shared platform-neutral behavior."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.action.models import ActionTarget
from app.comparison.pricing import PricingEngine, PricingRule, PricingRuleType, PricingStatus
from app.core.safety import SafetyDecision, SafetyGuard
from app.observation.models import Observation
from app.parser.price import Price
from app.platform.models import (
    AdapterActionDecision,
    AdapterExtraction,
    NormalizedProduct,
    PlatformPageType,
    PlatformProduct,
)


class BasePlatformAdapter:
    """Compatibility layer shared by browser, fixture, and mock adapters.

    Existing ``extract_*`` methods remain the implementation hooks. The
    explicit ``parse_*`` names make the architecture readable to callers and
    allow adding a platform without changing Runtime, Agent, or Workflow.
    """

    platform_id: str

    def identify_page(self, observation: Observation) -> PlatformPageType:
        raise NotImplementedError

    def extract_products(self, observation: Observation) -> AdapterExtraction:
        raise NotImplementedError

    def extract_product(self, observation: Observation) -> AdapterExtraction:
        raise NotImplementedError

    def parse_products(self, observation: Observation) -> AdapterExtraction:
        return self.extract_products(observation)

    def parse_product_detail(self, observation: Observation) -> AdapterExtraction:
        return self.extract_product(observation)

    def normalize_product(self, product: PlatformProduct) -> NormalizedProduct:
        base_price = product.original_price or product.price
        effective_price = self._effective_price(product)
        quantity = product.specification.primary_quantity
        total_quantity = quantity.total_quantity if quantity else None
        return NormalizedProduct(
            platform=self.platform_id,
            title=product.raw_title,
            product_name_raw=product.identity.name,
            product_name_normalized=product.identity.normalized_name,
            base_price=base_price,
            displayed_price=product.displayed_price or product.price,
            original_price=product.original_price,
            effective_price=effective_price,
            effective_unit_price=(effective_price.amount / total_quantity if effective_price and total_quantity else None),
            currency=(base_price.currency if base_price else "CNY"),
            price_status=product.price_status,
            price_evidence=product.price_evidence,
            quantity=quantity,
            specification=product.specification,
            seller=product.seller,
            store=product.seller,
            product_id=product.product_id,
            product_url=product.product_url,
            confidence=product.confidence,
            extraction_source=product.extraction_source,
        )

    def safety_boundary(self, observation: Observation) -> SafetyDecision:
        if self.identify_page(observation) in {
            PlatformPageType.ORDER_CONFIRM,
            PlatformPageType.PAYMENT,
        }:
            return SafetyDecision.STOP
        text = " ".join(
            value
            for node in observation.nodes
            for value in (node.text, node.content_description)
            if value
        )
        return SafetyGuard().evaluate(text).decision

    @staticmethod
    def _effective_price(product: PlatformProduct) -> Price | None:
        if product.price is None:
            return None
        rules: list[PricingRule] = []
        for promotion in product.promotions:
            if promotion.discount_amount is None and promotion.discount_ratio is None:
                continue
            confirmed = promotion.threshold_amount is None or (
                promotion.threshold_amount is not None and product.price.amount >= promotion.threshold_amount
            )
            if promotion.kind.value == "second_item_discount":
                confirmed = confirmed and product.specification.primary_quantity is not None and product.specification.primary_quantity.count == 2
                rule_type = PricingRuleType.MULTI_ITEM
            elif promotion.kind.value == "coupon":
                rule_type = PricingRuleType.COUPON
            else:
                rule_type = PricingRuleType.DIRECT_DISCOUNT
            rules.append(
                PricingRule(
                    rule_type=rule_type,
                    amount=promotion.discount_amount,
                    ratio=promotion.discount_ratio,
                    threshold_amount=promotion.threshold_amount,
                    condition_confirmed=confirmed,
                    evidence=promotion.raw_text,
                )
            )
        result = PricingEngine().calculate(product.price.amount, rules, order_subtotal=product.price.amount)
        if result.status is PricingStatus.UNRESOLVED or result.effective_price is None:
            return None
        return product.price.model_copy(update={"amount": result.effective_price})


@runtime_checkable
class PlatformAdapter(Protocol):
    platform_id: str

    def identify_platform(self, observation: Observation) -> bool:
        ...

    def identify_page(self, observation: Observation) -> PlatformPageType:
        ...

    def extract_products(self, observation: Observation) -> AdapterExtraction:
        ...

    def extract_product(self, observation: Observation) -> AdapterExtraction:
        ...

    def parse_products(self, observation: Observation) -> AdapterExtraction:
        ...

    def parse_product_detail(self, observation: Observation) -> AdapterExtraction:
        ...

    def normalize_product(self, product: PlatformProduct) -> NormalizedProduct:
        ...

    def safety_boundary(self, observation: Observation) -> SafetyDecision:
        ...

    def extract_price_promotions(self, observation: Observation) -> AdapterExtraction:
        ...

    def selector_candidates(self, observation: Observation, role: str) -> list[ActionTarget]:
        ...

    def build_platform_hints(self, observation: Observation) -> dict[str, list[str]]:
        ...

    def add_to_cart_decision(
        self,
        observation: Observation,
        *,
        safe_mode: bool,
        allow_cart: bool,
    ) -> AdapterActionDecision:
        ...
