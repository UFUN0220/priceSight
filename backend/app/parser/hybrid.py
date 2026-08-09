"""Rule-first product parsing with structured LLM fallback for ambiguity."""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.core.exceptions import ProviderError
from app.llm.base import LLMProvider, LLMRequest
from app.parser.models import (
    LLMParseSuggestion,
    ParseResult,
    ParseSource,
    ProductIdentity,
    ProductSpecification,
)
from app.parser.product import ProductParser


class HybridProductParser:
    """Use rules for confident cases and one structured fallback for ambiguous cases."""

    def __init__(
        self,
        provider: LLMProvider,
        rule_parser: ProductParser | None = None,
        confidence_threshold: float = 0.75,
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        self.provider = provider
        self.rule_parser = rule_parser or ProductParser()
        self.confidence_threshold = confidence_threshold

    def parse(self, text: str) -> ParseResult:
        rule_result = self.rule_parser.parse(text)
        if not rule_result.ambiguous and rule_result.confidence >= self.confidence_threshold:
            return rule_result
        try:
            response = self.provider.complete(
                LLMRequest(
                    system_prompt=(
                        "Return only JSON matching LLMParseSuggestion. "
                        "Do not return Markdown or additional fields."
                    ),
                    prompt=self._prompt(text, rule_result),
                )
            )
            suggestion = LLMParseSuggestion.model_validate_json(response.content)
        except (ProviderError, ValidationError, ValueError) as error:
            return rule_result.model_copy(
                update={
                    "source": ParseSource.RULE_FALLBACK,
                    "llm_fallback_attempted": True,
                    "fallback_reason": f"structured fallback unavailable: {type(error).__name__}",
                }
            )
        return ParseResult(
            original_text=text,
            normalized_text=rule_result.normalized_text,
            product_identity=ProductIdentity(
                original_text=text,
                name=suggestion.product_name,
                normalized_name=suggestion.normalized_product_name,
            ),
            specification=ProductSpecification(
                original_text=rule_result.normalized_text,
                primary_quantity=suggestion.quantity,
                components=[suggestion.quantity] if suggestion.quantity else [],
                package_type=rule_result.specification.package_type,
                ambiguous=suggestion.confidence < self.confidence_threshold,
                confidence=suggestion.confidence,
            ),
            promotions=suggestion.promotions or rule_result.promotions,
            confidence=suggestion.confidence,
            ambiguous=suggestion.confidence < self.confidence_threshold,
            source=ParseSource.LLM,
            llm_fallback_attempted=True,
        )

    @staticmethod
    def _prompt(text: str, rule_result: ParseResult) -> str:
        payload = {
            "raw_product_text": text,
            "rule_candidate": rule_result.model_dump(mode="json"),
            "instruction": "Resolve only the ambiguous identity/specification fields for this one product.",
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
