"""Conservative product/specification matching for cross-platform comparison."""

from __future__ import annotations

import re

from app.comparison.models import NormalizedRequirement, NormalizedOffer
from app.parser.product import ProductParser


class ProductMatcher:
    """Match only equivalent identity and measurable specification."""

    def __init__(self, parser: ProductParser | None = None) -> None:
        self.parser = parser or ProductParser()
        self.aliases = {
            "coca cola": "可口可乐",
            "coca-cola": "可口可乐",
            "可口可樂": "可口可乐",
        }

    def requirement(self, text: str) -> NormalizedRequirement:
        parsed = self.parser.parse(text)
        return NormalizedRequirement(
            raw_text=text,
            identity=parsed.product_identity,
            specification=parsed.specification,
        )

    def match(self, requirement: NormalizedRequirement, offer: NormalizedOffer) -> tuple[bool, str]:
        required_name = self._canonical(requirement.identity.normalized_name)
        offer_name = self._canonical(offer.identity.normalized_name)
        if not required_name or required_name != offer_name:
            return False, "normalized product names differ"
        required_quantity = requirement.specification.primary_quantity
        offer_quantity = offer.specification.primary_quantity
        if required_quantity is None or offer_quantity is None:
            return False, "quantity is missing or ambiguous"
        if required_quantity.count != offer_quantity.count:
            return False, "package counts differ"
        if required_quantity.normalized_content_unit != offer_quantity.normalized_content_unit:
            return False, "normalized units differ"
        if required_quantity.normalized_content_amount != offer_quantity.normalized_content_amount:
            return False, "normalized content amounts differ"
        return True, "product identity and specification match"

    def _canonical(self, name: str) -> str:
        normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", name.casefold()).strip()
        return self.aliases.get(normalized, normalized)
