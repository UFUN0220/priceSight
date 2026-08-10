"""Tests for the deterministic effective-price contract."""

from decimal import Decimal

from app.comparison.pricing import (
    PricingEngine,
    PricingRule,
    PricingRuleType,
    PricingStatus,
)


def test_direct_coupon_is_calculated_with_decimal() -> None:
    result = PricingEngine().calculate(
        Decimal("99.90"),
        [
            PricingRule(
                rule_type=PricingRuleType.COUPON,
                amount=Decimal("10"),
                condition_confirmed=True,
                evidence="10元券",
            )
        ],
    )

    assert result.status is PricingStatus.RESOLVED
    assert result.effective_price == Decimal("89.90")
    assert result.discount_amount == Decimal("10")


def test_threshold_discount_without_subtotal_is_unresolved() -> None:
    result = PricingEngine().calculate(
        Decimal("99"),
        [
            PricingRule(
                rule_type=PricingRuleType.THRESHOLD_DISCOUNT,
                amount=Decimal("10"),
                threshold_amount=Decimal("199"),
                condition_confirmed=False,
                evidence="满199减10",
            )
        ],
    )

    assert result.status is PricingStatus.UNRESOLVED
    assert result.effective_price is None


def test_shipping_fee_is_added_only_when_evidenced() -> None:
    result = PricingEngine().calculate(
        Decimal("20"),
        [
            PricingRule(
                rule_type=PricingRuleType.SHIPPING_FEE,
                amount=Decimal("3"),
                condition_confirmed=True,
                evidence="配送费3元",
            )
        ],
    )

    assert result.status is PricingStatus.RESOLVED
    assert result.effective_price == Decimal("23")
