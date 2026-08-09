"""Tests for deterministic product quantity, specification, and hybrid parsing."""

import json

from app.llm.base import LLMResponse
from app.llm.fake import FakeLLMProvider
from app.parser.hybrid import HybridProductParser
from app.parser.models import ParseSource, ParserSource, PromotionType, Unit
from app.parser.product import ProductParser


def test_measurement_and_package_count_are_separate() -> None:
    result = ProductParser().parse("农夫山泉 550ml×12瓶")
    quantity = result.specification.primary_quantity

    assert quantity is not None
    assert result.product_identity.name == "农夫山泉"
    assert quantity.content_amount == 550
    assert quantity.content_unit is Unit.ML
    assert quantity.count == 12
    assert quantity.container_unit is Unit.BOTTLE
    assert quantity.normalized_content_amount == 550
    assert result.confidence >= 0.9
    assert result.parser_source is ParserSource.RULE
    assert result.candidate_count == 1
    assert result.reason_code == "deterministic_confident"


def test_liter_and_kilogram_units_normalize_to_base_units() -> None:
    liter = ProductParser().parse("1L×2瓶").specification.primary_quantity
    kilogram = ProductParser().parse("250g*3袋").specification.primary_quantity

    assert liter is not None and liter.normalized_content_amount == 1000
    assert liter.normalized_content_unit is Unit.ML
    assert kilogram is not None and kilogram.normalized_content_amount == 250
    assert kilogram.normalized_content_unit is Unit.G


def test_count_only_package_and_gift_are_not_conflated() -> None:
    cups = ProductParser().parse("咖啡 2杯装")
    gift = ProductParser().parse("矿泉水 1L×2 + 赠250ml×2")

    assert cups.specification.primary_quantity is not None
    assert cups.specification.primary_quantity.count == 2
    assert cups.specification.primary_quantity.content_unit is Unit.CUP
    assert gift.specification.primary_quantity is not None
    assert gift.specification.primary_quantity.count == 2
    assert len(gift.promotions) == 1
    assert gift.promotions[0].kind is PromotionType.GIFT
    assert gift.promotions[0].gift_quantity is not None
    assert gift.promotions[0].gift_quantity.content_amount == 250


def test_buy_get_and_combo_are_marked_as_promotions_or_ambiguity() -> None:
    buy_get = ProductParser().parse("零食 买2赠1")
    combo = ProductParser().parse("双人套餐")

    assert buy_get.product_identity.name == "零食"
    assert buy_get.promotions[0].kind is PromotionType.BUY_GET
    assert buy_get.ambiguous is True
    assert buy_get.reason_code == "ambiguous_missing_primary_quantity"
    assert combo.specification.package_type == "combo"
    assert combo.ambiguous is True
    assert combo.reason_code == "ambiguous_combo_semantics"


def test_hybrid_parser_does_not_call_llm_for_confident_rule_result() -> None:
    provider = FakeLLMProvider()
    result = HybridProductParser(provider).parse("可口可乐 330ml*6罐")

    assert result.source is ParseSource.RULE
    assert result.llm_fallback_attempted is False
    assert provider.calls == []


def test_hybrid_parser_uses_structured_llm_only_for_ambiguous_result() -> None:
    response = {
        "product_name": "双人套餐",
        "normalized_product_name": "双人套餐",
        "quantity": None,
        "promotions": [],
        "confidence": 0.9,
        "reason_summary": "套餐是组合商品",
    }
    provider = FakeLLMProvider(
        [LLMResponse(content=json.dumps(response, ensure_ascii=False), provider="fake")]
    )

    result = HybridProductParser(provider).parse("双人套餐")

    assert result.source is ParseSource.LLM
    assert result.parser_source is ParserSource.HYBRID
    assert result.llm_fallback_attempted is True
    assert result.llm_schema_valid is True
    assert result.reason_code == "llm_structured_resolution"
    assert len(provider.calls) == 1
    assert "raw_product_text" in provider.calls[0].prompt


def test_hybrid_parser_keeps_rule_result_when_model_output_is_malformed() -> None:
    provider = FakeLLMProvider([LLMResponse(content="not-json", provider="fake")])

    result = HybridProductParser(provider).parse("双人套餐")

    assert result.source is ParseSource.RULE_FALLBACK
    assert result.parser_source is ParserSource.HYBRID
    assert result.llm_fallback_attempted is True
    assert result.llm_schema_valid is False
    assert result.reason_code == "llm_schema_or_provider_failure"
    assert result.fallback_reason is not None
