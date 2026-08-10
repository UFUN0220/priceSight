"""Deterministic displayed/effective price parsing with a fail-closed boundary."""

import re
from dataclasses import dataclass
from decimal import Decimal

from app.parser.models import Quantity

from pydantic import BaseModel, ConfigDict, Field


class Price(BaseModel):
    """Typed price DTO shared by displayed and effective price results."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0)
    currency: str = "CNY"
    original_text: str


class PriceParser:
    """Deterministic price extraction for platform adapters."""

    _currency_pattern = re.compile(r"(?:¥|￥|人民币|RMB)\s*(\d+(?:\.\d{1,2})?)", re.IGNORECASE)
    _label_pattern = re.compile(
        r"(?:到手价|券后价|券后|实付|优惠后|特价|售价|现价|促销价|秒杀价)\s*[:：]?\s*"
        r"(?:¥|￥|人民币|RMB)?\s*(\d+(?:\.\d{1,2})?)\s*元?",
        re.IGNORECASE,
    )
    _yuan_pattern = re.compile(r"(?<![-~～])\b(\d+(?:\.\d{1,2})?)\s*元")
    _range_pattern = re.compile(r"\d+(?:\.\d{1,2})?\s*[-~～]\s*\d+(?:\.\d{1,2})?\s*元")
    _effective_label_pattern = re.compile(
        r"(?:到手价|券后价|券后|实付|优惠后)\s*[:：]?\s*"
        r"(?:¥|￥|人民币|RMB)?\s*(?P<amount>\d+(?:\.\d{1,2})?)\s*元?",
        re.IGNORECASE,
    )
    _simple_coupon_pattern = re.compile(
        r"(?P<base>\d+(?:\.\d{1,2})?)\s*元[^。；;]{0,12}?"
        r"(?P<discount>\d+(?:\.\d{1,2})?)\s*元?券",
        re.IGNORECASE,
    )
    _threshold_promotion_pattern = re.compile(r"满\s*\d+(?:\.\d+)?\s*减\s*\d+(?:\.\d+)?")
    _second_item_pattern = re.compile(r"第二(?:件|双)\s*(?P<offer>半价|免费|5折)")

    def parse(self, text: str) -> Price | None:
        """Backward-compatible direct price extraction used by adapters/tests."""

        if self._range_pattern.search(text):
            return None
        match = self._label_pattern.search(text) or self._currency_pattern.search(text) or self._yuan_pattern.search(text)
        if match is None:
            return None
        return Price(amount=Decimal(match.group(1)), original_text=match.group(0))

    def parse_prices(self, text: str, quantity: Quantity | None = None) -> "ParsedPrices":
        """Return listed and deterministically reproducible effective prices.

        Threshold promotions are intentionally not evaluated: satisfying the
        threshold is not knowable from a product title alone.
        """

        if self._range_pattern.search(text):
            return ParsedPrices(displayed=None, effective=None, effective_kind=None)

        effective_match = self._effective_label_pattern.search(text)
        displayed = self._displayed_price(text, effective_match)
        if effective_match is not None:
            effective = Price(
                amount=Decimal(effective_match.group("amount")),
                original_text=effective_match.group(0),
            )
            return ParsedPrices(displayed=displayed, effective=effective, effective_kind="after_sale")

        coupon = self._simple_coupon_pattern.search(text)
        if coupon is not None and self._threshold_promotion_pattern.search(text) is None:
            base = Decimal(coupon.group("base"))
            discount = Decimal(coupon.group("discount"))
            if base > discount:
                return ParsedPrices(
                    displayed=displayed,
                    effective=Price(amount=base - discount, original_text=coupon.group(0)),
                    effective_kind="coupon",
                )

        second = self._second_item_pattern.search(text)
        if second is not None:
            if quantity is not None and quantity.count == 2 and displayed is not None:
                ratio = Decimal("0.5") if second.group("offer") in {"免费"} else Decimal("0.75")
                return ParsedPrices(
                    displayed=displayed,
                    effective=Price(amount=displayed.amount * ratio, original_text=second.group(0)),
                    effective_kind="second_item_discount",
                )
            return ParsedPrices(displayed=displayed, effective=None, effective_kind=None)

        if displayed is not None and self._threshold_promotion_pattern.search(text) is None:
            return ParsedPrices(displayed=displayed, effective=displayed, effective_kind="displayed")
        return ParsedPrices(displayed=displayed, effective=None, effective_kind=None)

    def _displayed_price(self, text: str, effective_match: re.Match[str] | None) -> Price | None:
        if effective_match is None:
            return self.parse(text)
        without_effective = text[: effective_match.start()] + text[effective_match.end() :]
        return self.parse(without_effective)


@dataclass(frozen=True)
class ParsedPrices:
    displayed: Price | None
    effective: Price | None
    effective_kind: str | None
