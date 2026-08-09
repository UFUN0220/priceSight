"""Rule-first product identity and specification parser."""

from __future__ import annotations

import re

from app.parser.models import (
    ParseResult,
    ProductIdentity,
    ProductSpecification,
)
from app.parser.quantity import QuantityParser
from app.parser.specification import PromotionParser


class ProductParser:
    """Parse one product title without sending a product list to an LLM."""

    def __init__(
        self,
        quantity_parser: QuantityParser | None = None,
        promotion_parser: PromotionParser | None = None,
    ) -> None:
        self.quantity_parser = quantity_parser or QuantityParser()
        self.promotion_parser = promotion_parser or PromotionParser(self.quantity_parser)

    def parse(self, text: str) -> ParseResult:
        normalized = self.quantity_parser.normalize(text)
        primary_match = self.quantity_parser.parse_first(normalized)
        promotions = self.promotion_parser.parse(normalized)
        components = [item.quantity for item in self.quantity_parser.parse_all(normalized)]
        primary_quantity = primary_match.quantity if primary_match else None
        package_type = "combo" if any(item.kind.value == "combo" for item in promotions) else None
        identity_name = self._identity_name(normalized, primary_match.start if primary_match else None)
        ambiguous = primary_quantity is None or package_type == "combo"
        confidence = primary_quantity.confidence if primary_quantity else 0.45
        if package_type == "combo":
            confidence = min(confidence, 0.58)
        if promotions and primary_quantity is not None and package_type != "combo":
            confidence = min(1.0, confidence + 0.01)
        return ParseResult(
            original_text=text,
            normalized_text=normalized,
            product_identity=ProductIdentity(
                original_text=text,
                name=identity_name,
                normalized_name=identity_name.casefold(),
            ),
            specification=ProductSpecification(
                original_text=normalized,
                primary_quantity=primary_quantity,
                components=components[:1],
                package_type=package_type,
                ambiguous=ambiguous,
                confidence=confidence,
            ),
            promotions=promotions,
            confidence=confidence,
            ambiguous=ambiguous,
        )

    @staticmethod
    def _identity_name(text: str, quantity_start: int | None) -> str:
        candidate = text[:quantity_start] if quantity_start is not None else text
        if quantity_start is None:
            candidate = re.sub(r"\s*(?:买\d+赠\d+|赠.*)$", "", candidate).strip()
        candidate = re.sub(r"\s*[+＋]\s*$", "", candidate).strip(" -_:")
        if not candidate:
            candidate = re.sub(r"\s*(?:买\d+赠\d+|赠.*)$", "", text).strip()
        return candidate or text
