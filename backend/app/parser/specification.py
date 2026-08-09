"""Deterministic package specification and promotion parsing."""

from __future__ import annotations

import re
from decimal import Decimal

from app.parser.models import Promotion, PromotionType
from app.parser.quantity import QuantityParser


class PromotionParser:
    """Keep promotional quantities separate from purchased quantities."""

    _buy_get = re.compile(r"买\s*(\d+)\s*(?:赠|送)\s*(\d+)")

    def __init__(self, quantity_parser: QuantityParser | None = None) -> None:
        self.quantity_parser = quantity_parser or QuantityParser()

    def parse(self, text: str) -> list[Promotion]:
        normalized = self.quantity_parser.normalize(text)
        promotions: list[Promotion] = []
        for match in self._buy_get.finditer(normalized):
            promotions.append(
                Promotion(
                    raw_text=match.group(0),
                    kind=PromotionType.BUY_GET,
                    buy_count=int(match.group(1)),
                    gift_count=int(match.group(2)),
                    confidence=0.98,
                )
            )

        gift_index = normalized.find("赠")
        if gift_index >= 0:
            gift_text = normalized[gift_index + 1 :]
            gift_match = self.quantity_parser.parse_first(gift_text)
            if gift_match is not None and not any(item.kind is PromotionType.BUY_GET for item in promotions):
                promotions.append(
                    Promotion(
                        raw_text=normalized[gift_index:].strip(),
                        kind=PromotionType.GIFT,
                        gift_count=gift_match.quantity.count,
                        gift_quantity=gift_match.quantity,
                        confidence=0.94,
                    )
                )

        if "双人套餐" in normalized or "组合装" in normalized or "组合" in normalized:
            promotions.append(
                Promotion(
                    raw_text=normalized,
                    kind=PromotionType.COMBO,
                    confidence=0.72,
                )
            )
        coupon = re.search(r"优惠券(?:\s*满\s*(\d+(?:\.\d+)?)\s*减\s*(\d+(?:\.\d+)?))?", normalized)
        if coupon is not None:
            promotions.append(
                Promotion(
                    raw_text=coupon.group(0),
                    kind=PromotionType.COUPON,
                    threshold_amount=Decimal(coupon.group(1)) if coupon.group(1) else None,
                    discount_amount=Decimal(coupon.group(2)) if coupon.group(2) else None,
                    confidence=0.9 if coupon.group(1) else 0.75,
                )
            )
        return promotions
