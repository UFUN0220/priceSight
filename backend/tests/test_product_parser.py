"""Tests for deterministic product quantity, specification, and hybrid parsing."""

import json
from decimal import Decimal

import pytest

from app.llm.base import LLMResponse
from app.llm.fake import FakeLLMProvider
from app.parser.hybrid import HybridProductParser
from app.parser.models import ParseSource, ParserSource, PromotionType, Unit
from app.parser.product import ProductParser
from app.parser.price import PriceParser


def test_price_parser_supports_yuan_and_labeled_current_price() -> None:
    parser = PriceParser()

    assert parser.parse("落地扇 199元 满100减30") is not None
    assert parser.parse("落地扇 199元 满100减30").amount == 199
    labeled_price = parser.parse("早餐奶 原价49.9 限时特价39.9 箱装")
    assert labeled_price is not None and labeled_price.amount == Decimal("39.9")


def test_price_parser_rejects_price_range_without_selecting_an_endpoint() -> None:
    assert PriceParser().parse("运动手表 199-399元 多款") is None


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


def test_quantity_parser_handles_prefix_counts_and_non_decimal_package_units() -> None:
    bottle = ProductParser().parse("红酒 6瓶 750ml").specification.primary_quantity
    pairs = ProductParser().parse("袜子 5双装").specification.primary_quantity
    shoes = ProductParser().parse("运动鞋 两双").specification.primary_quantity

    assert bottle is not None and bottle.count == 6 and bottle.container_unit is Unit.BOTTLE
    assert pairs is not None and pairs.count == 5 and pairs.container_unit is Unit.PAIR
    assert shoes is not None and shoes.count == 2 and shoes.container_unit is Unit.PAIR


def test_quantity_parser_does_not_treat_storage_gb_as_weight_g() -> None:
    result = ProductParser().parse("平板电脑 128GB 灰色")

    assert result.specification.primary_quantity is None
    assert result.specification.components[0].content_unit is Unit.GB


def test_digital_and_length_units_are_schema_valid_specification_components() -> None:
    parser = ProductParser()

    digital = parser.parse("平板电脑 12GB+256GB")
    length = parser.parse("耳机 驱动单元 40mm")
    inch = parser.parse("显示器 27inch")

    assert digital.specification.primary_quantity is None
    assert [item.content_unit for item in digital.specification.components] == [Unit.GB, Unit.GB]
    assert length.specification.primary_quantity is None
    assert length.specification.components[0].content_unit is Unit.MM
    assert inch.specification.components[0].content_unit is Unit.INCH


def test_invalid_units_are_rejected_by_structured_quantity_schema() -> None:
    from pydantic import ValidationError
    from app.parser.models import Quantity

    for invalid in ("foobar", "unknown_unit", "abc123"):
        with pytest.raises(ValidationError):
            Quantity(raw_text=invalid, content_amount=1, content_unit=invalid)


def test_package_type_requires_explicit_packaging_evidence() -> None:
    parser = ProductParser()

    assert parser.parse("月饼礼盒 8枚").specification.package_type == "box"
    assert parser.parse("早餐奶 箱装").specification.package_type == "box"
    assert parser.parse("垃圾袋 袋装").specification.package_type == "bag"
    assert parser.parse("运动鞋 黑色").specification.package_type is None


def test_promotional_or_noisy_titles_are_routed_to_semantic_review() -> None:
    parser = ProductParser()

    assert parser.parse("早餐奶 原价49.9 限时特价39.9 箱装").ambiguous is True
    assert parser.parse("运动鞋 第二双半价 两双").ambiguous is True
    assert parser.parse("商品 黑色 多规格").ambiguous is True


def test_effective_price_parser_is_deterministic_and_fail_closed() -> None:
    price_parser = PriceParser()

    coupon = price_parser.parse_prices("商品 99元，10元券")
    assert coupon.displayed is not None and coupon.displayed.amount == Decimal("99")
    assert coupon.effective is not None and coupon.effective.amount == Decimal("89")

    threshold = price_parser.parse_prices("商品 199元 满199减10")
    assert threshold.displayed is not None and threshold.displayed.amount == Decimal("199")
    assert threshold.effective is None

    assert price_parser.parse_prices("商品 199-399元").displayed is None
    assert price_parser.parse_prices("商品 券后89元").displayed is None
    assert price_parser.parse_prices("商品 券后89元").effective is not None


def test_second_item_promotion_and_effective_unit_price_require_two_items() -> None:
    result = ProductParser().parse("运动鞋 299元 第二双半价 两双")
    quantity = result.specification.primary_quantity
    assert quantity is not None and quantity.count == 2
    assert result.promotions[0].kind is PromotionType.SECOND_ITEM_DISCOUNT

    prices = PriceParser().parse_prices("运动鞋 299元 第二双半价 两双", quantity)
    assert prices.effective is not None and prices.effective.amount == Decimal("224.25")
    unknown_quantity = PriceParser().parse_prices("运动鞋 299元 第二双半价")
    assert unknown_quantity.effective is None


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
