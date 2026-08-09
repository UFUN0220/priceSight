"""Rule-first product identity and specification parser."""

from __future__ import annotations

import re

from app.parser.models import (
    ParseResult,
    Promotion,
    ProductIdentity,
    ProductSpecification,
)
from app.parser.quantity import QuantityMatch, QuantityParser
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
        normalized = self.normalize(text)
        candidates = self.extract_candidates(normalized)
        primary_match = candidates[0] if candidates else None
        promotions = self.promotion_parser.parse(normalized)
        components = [item.quantity for item in candidates]
        primary_quantity = primary_match.quantity if primary_match else None
        package_type = "combo" if any(item.kind.value == "combo" for item in promotions) else None
        identity_name = self._identity_name(normalized, primary_match.start if primary_match else None)
        ambiguous = primary_quantity is None or package_type == "combo"
        confidence = primary_quantity.confidence if primary_quantity else 0.45
        if package_type == "combo":
            confidence = min(confidence, 0.58)
        if promotions and primary_quantity is not None and package_type != "combo":
            confidence = min(1.0, confidence + 0.01)
        reason_code, reason = self._reason(ambiguous, package_type, promotions, candidates)
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
            parser_source="RULE",
            candidate_count=len(candidates),
            reason_code=reason_code,
            reason=reason,
        )

    def normalize(self, text: str) -> str:
        """Stage 1: normalize Unicode and common quantity separators."""

        return self.quantity_parser.normalize(text)

    def extract_candidates(self, normalized_text: str) -> list[QuantityMatch]:
        """Stage 2: extract measurable quantity candidates for deterministic parsing."""

        return self.quantity_parser.parse_all(normalized_text)

    @staticmethod
    def _reason(
        ambiguous: bool,
        package_type: str | None,
        promotions: list[Promotion],
        candidates: list[QuantityMatch],
    ) -> tuple[str, str]:
        if package_type == "combo":
            return "ambiguous_combo_semantics", "组合商品需要判断组件关系，交给结构化 LLM 复核。"
        if not candidates:
            return "ambiguous_missing_primary_quantity", "未提取到主数量，商品核心名称或规格可能需要语义判断。"
        if promotions:
            return "deterministic_quantity_and_promotion", "数量与简单促销已由规则解析，赠品/促销数量保持分离。"
        if ambiguous:
            return "ambiguous_deterministic_candidate", "规则候选存在但置信度不足，需要结构化 LLM 复核。"
        return "deterministic_confident", "数量、单位和商品名候选满足规则解析置信度门槛。"

    @staticmethod
    def _identity_name(text: str, quantity_start: int | None) -> str:
        candidate = text[:quantity_start] if quantity_start is not None else text
        if quantity_start is None:
            candidate = re.sub(r"\s*(?:买\d+赠\d+|赠.*)$", "", candidate).strip()
        candidate = re.sub(r"\s*[+＋]\s*$", "", candidate).strip(" -_:")
        if not candidate:
            candidate = re.sub(r"\s*(?:买\d+赠\d+|赠.*)$", "", text).strip()
        return candidate or text
