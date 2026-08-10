"""Deterministic effective-price calculation over explicitly evidenced rules."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PricingStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class PricingRuleType(StrEnum):
    DIRECT_DISCOUNT = "direct_discount"
    COUPON = "coupon"
    THRESHOLD_DISCOUNT = "threshold_discount"
    MULTI_ITEM = "multi_item"
    SHIPPING_FEE = "shipping_fee"
    MEMBERSHIP_DISCOUNT = "membership_discount"


class PricingRule(BaseModel):
    """A discount or fee with an explicit evidence/condition boundary."""

    model_config = ConfigDict(extra="forbid")

    rule_type: PricingRuleType
    amount: Decimal | None = Field(default=None, gt=0)
    ratio: Decimal | None = Field(default=None, gt=0, le=1)
    threshold_amount: Decimal | None = Field(default=None, gt=0)
    condition_confirmed: bool = False
    evidence: str


class PricingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PricingStatus
    listed_price: Decimal | None = Field(default=None, gt=0)
    effective_price: Decimal | None = Field(default=None, gt=0)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    shipping_fee: Decimal = Field(default=Decimal("0"), ge=0)
    applied_rules: list[str] = Field(default_factory=list)
    reason: str


class PricingEngine:
    """Calculate only when every applied rule has sufficient evidence."""

    def calculate(
        self,
        listed_price: Decimal | None,
        rules: list[PricingRule],
        *,
        order_subtotal: Decimal | None = None,
    ) -> PricingResult:
        if listed_price is None:
            return PricingResult(status=PricingStatus.UNRESOLVED, reason="listed_price_missing")

        current = listed_price
        discount = Decimal("0")
        shipping = Decimal("0")
        applied: list[str] = []
        for rule in rules:
            if not rule.condition_confirmed:
                return PricingResult(
                    status=PricingStatus.UNRESOLVED,
                    listed_price=listed_price,
                    reason=f"rule_condition_unconfirmed:{rule.rule_type.value}",
                )
            if rule.rule_type is PricingRuleType.THRESHOLD_DISCOUNT:
                if order_subtotal is None or rule.threshold_amount is None or order_subtotal < rule.threshold_amount:
                    return PricingResult(
                        status=PricingStatus.UNRESOLVED,
                        listed_price=listed_price,
                        reason="threshold_discount_requires_order_subtotal",
                    )
            if rule.rule_type is PricingRuleType.SHIPPING_FEE:
                if rule.amount is None:
                    return PricingResult(
                        status=PricingStatus.UNRESOLVED,
                        listed_price=listed_price,
                        reason="shipping_fee_amount_missing",
                    )
                current += rule.amount
                shipping += rule.amount
                applied.append(rule.evidence)
                continue
            reduction = rule.amount or Decimal("0")
            if rule.ratio is not None:
                reduction = current * rule.ratio
            if reduction <= 0 or reduction > current:
                return PricingResult(
                    status=PricingStatus.UNRESOLVED,
                    listed_price=listed_price,
                    reason="discount_amount_invalid_or_exceeds_price",
                )
            current -= reduction
            discount += reduction
            applied.append(rule.evidence)

        return PricingResult(
            status=PricingStatus.RESOLVED,
            listed_price=listed_price,
            effective_price=max(Decimal("0.01"), current),
            discount_amount=discount,
            shipping_fee=shipping,
            applied_rules=applied,
            reason="all_pricing_rules_condition_confirmed",
        )
