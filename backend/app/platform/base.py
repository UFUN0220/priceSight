"""Platform adapter protocol; platform-specific selectors stay out of generic code."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.action.models import ActionTarget
from app.observation.models import Observation
from app.platform.models import AdapterActionDecision, AdapterExtraction, PlatformPageType


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
