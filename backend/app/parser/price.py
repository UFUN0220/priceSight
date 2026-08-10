"""Deterministic price extraction with auditable evidence and abstention."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.parser.models import Quantity
from pydantic import BaseModel, ConfigDict, Field


class PriceKind(StrEnum):
    DISPLAYED = "displayed"
    AFTER_SALE = "after_sale"
    ORIGINAL = "original"
    MEMBER = "member"
    STARTING = "starting"


class PriceResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    NEED_MORE_EVIDENCE = "NEED_MORE_EVIDENCE"


class PriceEvidence(BaseModel):
    """The smallest auditable unit behind one extracted price."""

    model_config = ConfigDict(extra="forbid")

    source_text: str
    source_node_id: str | None = None
    selector: str | None = None
    normalized_amount: Decimal
    parser: str = "deterministic_price_parser"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class Price(BaseModel):
    """Typed price DTO shared by displayed and effective price results."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0)
    currency: str = "CNY"
    original_text: str
    kind: PriceKind = PriceKind.DISPLAYED
    evidence: PriceEvidence | None = None


class PriceCandidate(BaseModel):
    """A price found on the page before deterministic ranking."""

    model_config = ConfigDict(extra="forbid")

    price: Price
    kind: PriceKind
    label: str | None = None
    evidence: PriceEvidence
    rank: int = Field(ge=0)


class PriceParser:
    """Extract and rank prices without selecting the lowest number."""

    _amount = r"(?:¥|￥|人民币|RMB)?\s*(?P<amount>\d+(?:\.\d{1,2})?)\s*元?"
    _currency_pattern = re.compile(
        r"(?:¥|￥|人民币|RMB)\s*(?P<amount>\d+(?:\.\d{1,2})?)", re.IGNORECASE
    )
    _effective_label_pattern = re.compile(
        rf"(?P<label>到手价|券后价|券后|实付|优惠后)\s*[:：]?\s*{_amount}",
        re.IGNORECASE,
    )
    _displayed_label_pattern = re.compile(
        rf"(?P<label>限时特价|特价|售价|现价|促销价|秒杀价|销售价)\s*[:：]?\s*{_amount}",
        re.IGNORECASE,
    )
    _original_label_pattern = re.compile(
        rf"(?P<label>原价|划线价|吊牌价)\s*[:：]?\s*{_amount}",
        re.IGNORECASE,
    )
    _member_label_pattern = re.compile(
        rf"(?P<label>会员价|VIP价|plus价)\s*[:：]?\s*{_amount}",
        re.IGNORECASE,
    )
    _starting_pattern = re.compile(
        r"(?P<amount>\d+(?:\.\d{1,2})?)\s*元?\s*起", re.IGNORECASE
    )
    _yuan_pattern = re.compile(r"(?<![\d.])(?P<amount>\d+(?:\.\d{1,2})?)\s*元")
    _range_pattern = re.compile(r"\d+(?:\.\d{1,2})?\s*[-~～]\s*\d+(?:\.\d{1,2})?\s*元")
    _simple_coupon_pattern = re.compile(
        r"(?P<base>\d+(?:\.\d{1,2})?)\s*元[^。；;]{0,12}?"
        r"(?P<discount>\d+(?:\.\d{1,2})?)\s*元?券",
        re.IGNORECASE,
    )
    _threshold_promotion_pattern = re.compile(r"满\s*\d+(?:\.\d+)?\s*减\s*\d+(?:\.\d+)?")
    _second_item_pattern = re.compile(r"第二(?:件|双)\s*(?P<offer>半价|免费|5折)")

    def parse(
        self,
        text: str,
        *,
        source_node_id: str | None = None,
        selector: str | None = None,
    ) -> Price | None:
        """Return the best directly displayed price for adapter compatibility."""

        if self._range_pattern.search(text):
            return None
        candidates = self._candidates(text, source_node_id=source_node_id, selector=selector)
        selected = self._select(candidates, preferred={PriceKind.DISPLAYED})
        if selected is None:
            selected = self._select(candidates, preferred={PriceKind.AFTER_SALE})
        return selected.price if selected is not None else None

    def parse_prices(
        self,
        text: str,
        quantity: Quantity | None = None,
        *,
        source_node_id: str | None = None,
        selector: str | None = None,
    ) -> "ParsedPrices":
        """Return ranked price candidates and only provable effective prices."""

        if self._range_pattern.search(text):
            return ParsedPrices(
                displayed=None,
                effective=None,
                effective_kind=None,
                candidates=[],
                status=PriceResolutionStatus.UNRESOLVED,
                reason="price_range_has_no_unique_sku_price",
            )

        candidates = self._candidates(text, source_node_id=source_node_id, selector=selector)
        displayed_candidate = self._select(candidates, preferred={PriceKind.DISPLAYED})
        displayed = displayed_candidate.price if displayed_candidate else None
        after_sale = self._select(candidates, preferred={PriceKind.AFTER_SALE})
        member = self._select(candidates, preferred={PriceKind.MEMBER})
        starting = self._select(candidates, preferred={PriceKind.STARTING})

        if self._has_conflict(candidates, {PriceKind.DISPLAYED}):
            return ParsedPrices(
                displayed=None,
                effective=None,
                effective_kind=None,
                candidates=candidates,
                status=PriceResolutionStatus.UNRESOLVED,
                reason="conflicting_displayed_price_candidates",
            )

        if after_sale is not None:
            return ParsedPrices(
                displayed=displayed,
                effective=after_sale.price,
                effective_kind=PriceKind.AFTER_SALE.value,
                candidates=candidates,
                status=PriceResolutionStatus.RESOLVED,
                reason="explicit_after_sale_price",
            )

        coupon = self._simple_coupon_pattern.search(text)
        if coupon is not None and self._threshold_promotion_pattern.search(text) is None:
            base = Decimal(coupon.group("base"))
            discount = Decimal(coupon.group("discount"))
            if base > discount:
                effective = self._derived_price(
                    base - discount,
                    coupon.group(0),
                    PriceKind.AFTER_SALE,
                    source_node_id,
                    selector,
                    0.90,
                )
                return ParsedPrices(
                    displayed=displayed,
                    effective=effective,
                    effective_kind="coupon",
                    candidates=candidates,
                    status=PriceResolutionStatus.RESOLVED,
                    reason="explicit_unconditional_coupon",
                )

        second = self._second_item_pattern.search(text)
        if second is not None:
            if quantity is not None and quantity.count == 2 and displayed is not None:
                ratio = Decimal("0.5") if second.group("offer") == "免费" else Decimal("0.75")
                effective = self._derived_price(
                    displayed.amount * ratio,
                    second.group(0),
                    PriceKind.AFTER_SALE,
                    source_node_id,
                    selector,
                    0.86,
                )
                return ParsedPrices(
                    displayed=displayed,
                    effective=effective,
                    effective_kind="second_item_discount",
                    candidates=candidates,
                    status=PriceResolutionStatus.RESOLVED,
                    reason="quantity_confirmed_second_item_discount",
                )
            return ParsedPrices(
                displayed=displayed,
                effective=None,
                effective_kind=None,
                candidates=candidates,
                status=PriceResolutionStatus.NEED_MORE_EVIDENCE,
                reason="second_item_discount_requires_quantity",
            )

        if self._threshold_promotion_pattern.search(text) or member is not None:
            reason = "threshold_discount_requires_order_subtotal" if self._threshold_promotion_pattern.search(text) else "member_price_requires_identity"
            return ParsedPrices(
                displayed=displayed,
                effective=None,
                effective_kind=None,
                candidates=candidates,
                status=PriceResolutionStatus.UNRESOLVED,
                reason=reason,
            )

        if displayed is not None:
            return ParsedPrices(
                displayed=displayed,
                effective=displayed,
                effective_kind=PriceKind.DISPLAYED.value,
                candidates=candidates,
                status=PriceResolutionStatus.RESOLVED,
                reason="single_current_price_candidate",
            )
        reason = "starting_price_requires_sku_selection" if starting is not None else "no_current_price_candidate"
        return ParsedPrices(
            displayed=None,
            effective=None,
            effective_kind=None,
            candidates=candidates,
            status=PriceResolutionStatus.NEED_MORE_EVIDENCE,
            reason=reason,
        )

    def _candidates(
        self,
        text: str,
        *,
        source_node_id: str | None,
        selector: str | None,
    ) -> list[PriceCandidate]:
        patterns = (
            (self._effective_label_pattern, PriceKind.AFTER_SALE, 100),
            (self._displayed_label_pattern, PriceKind.DISPLAYED, 80),
            (self._original_label_pattern, PriceKind.ORIGINAL, 20),
            (self._member_label_pattern, PriceKind.MEMBER, 10),
            (self._starting_pattern, PriceKind.STARTING, 5),
            (self._currency_pattern, PriceKind.DISPLAYED, 70),
            (self._yuan_pattern, PriceKind.DISPLAYED, 70),
        )
        candidates: list[PriceCandidate] = []
        occupied: set[tuple[int, int]] = set()
        for pattern, kind, rank in patterns:
            for match in pattern.finditer(text):
                span = (match.start(), match.end())
                amount = Decimal(match.group("amount"))
                if amount <= 0:
                    continue
                coupon_match = self._simple_coupon_pattern.search(text)
                if (
                    coupon_match is not None
                    and pattern in {self._currency_pattern, self._yuan_pattern}
                    and coupon_match.start() < match.start() < coupon_match.end()
                    and amount != Decimal(coupon_match.group("base"))
                ):
                    continue
                if any(start <= match.start() < end or match.start() <= start < match.end() for start, end in occupied):
                    continue
                evidence = PriceEvidence(
                    source_text=match.group(0),
                    source_node_id=source_node_id,
                    selector=selector,
                    normalized_amount=amount,
                    confidence=0.95 if kind in {PriceKind.AFTER_SALE, PriceKind.DISPLAYED} else 0.80,
                )
                candidates.append(
                    PriceCandidate(
                        price=Price(amount=amount, original_text=match.group(0), kind=kind, evidence=evidence),
                        kind=kind,
                        label=match.groupdict().get("label"),
                        evidence=evidence,
                        rank=rank,
                    )
                )
                occupied.add(span)
        return sorted(candidates, key=lambda candidate: (candidate.evidence.source_text, -candidate.rank))

    @staticmethod
    def _select(candidates: list[PriceCandidate], *, preferred: set[PriceKind]) -> PriceCandidate | None:
        matching = [candidate for candidate in candidates if candidate.kind in preferred]
        return max(matching, key=lambda candidate: candidate.rank, default=None)

    @staticmethod
    def _has_conflict(candidates: list[PriceCandidate], kinds: set[PriceKind]) -> bool:
        matching = [candidate for candidate in candidates if candidate.kind in kinds]
        if not matching:
            return False
        best_rank = max(candidate.rank for candidate in matching)
        amounts = {candidate.price.amount for candidate in matching if candidate.rank == best_rank}
        return len(amounts) > 1

    @staticmethod
    def _derived_price(
        amount: Decimal,
        source_text: str,
        kind: PriceKind,
        source_node_id: str | None,
        selector: str | None,
        confidence: float,
    ) -> Price:
        evidence = PriceEvidence(
            source_text=source_text,
            source_node_id=source_node_id,
            selector=selector,
            normalized_amount=amount,
            parser="deterministic_pricing_rule",
            confidence=confidence,
        )
        return Price(amount=amount, original_text=source_text, kind=kind, evidence=evidence)


@dataclass(frozen=True)
class ParsedPrices:
    displayed: Price | None
    effective: Price | None
    effective_kind: str | None
    candidates: list[PriceCandidate]
    status: PriceResolutionStatus = PriceResolutionStatus.RESOLVED
    reason: str | None = None
