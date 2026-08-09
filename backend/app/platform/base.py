"""Platform adapter contract and shared platform-neutral behavior."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.action.models import ActionTarget
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

    def parse_products(self, observation: Observation) -> AdapterExtraction:
        return self.extract_products(observation)

    def parse_product_detail(self, observation: Observation) -> AdapterExtraction:
        return self.extract_product(observation)

    def normalize_product(self, product: PlatformProduct) -> NormalizedProduct:
        base_price = product.original_price or product.price
        effective_price = self._effective_price(product)
        return NormalizedProduct(
            platform=self.platform_id,
            title=product.raw_title,
            base_price=base_price,
            effective_price=effective_price,
            quantity=product.specification.primary_quantity,
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
        discount = sum(
            (promotion.discount_amount or 0)
            for promotion in product.promotions
            if promotion.discount_amount is not None
        )
        amount = max(Decimal("0.01"), product.price.amount - discount)
        return product.price.model_copy(update={"amount": amount})


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
