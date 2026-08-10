"""Cross-platform normalized offer comparison with conservative cache use."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from app.cache.offer import OfferCache
from app.comparison.matcher import ProductMatcher
from app.comparison.models import CacheEvent, ComparisonResult, FinalPrice, NormalizedOffer
from app.comparison.pricing import PricingEngine, PricingRule, PricingRuleType, PricingStatus
from app.observation.models import Observation
from app.platform.base import PlatformAdapter
from app.parser.models import PromotionType
from app.parser.price import PriceResolutionStatus


class ComparisonEngine:
    def __init__(
        self,
        matcher: ProductMatcher | None = None,
        cache: OfferCache | None = None,
    ) -> None:
        self.matcher = matcher or ProductMatcher()
        self.cache = cache or OfferCache()

    def compare(
        self,
        requirement_text: str,
        sources: Iterable[tuple[PlatformAdapter, Observation]],
    ) -> ComparisonResult:
        requirement = self.matcher.requirement(requirement_text)
        offers: list[NormalizedOffer] = []
        cache_hits = 0
        cache_misses = 0
        cache_events: list[CacheEvent] = []
        for adapter, observation in sources:
            extraction = adapter.parse_products(observation)
            store = observation.package_name or adapter.platform_id
            if not extraction.recognized:
                continue
            for product in extraction.products:
                key = self.cache.key(
                    platform=adapter.platform_id,
                    store=store,
                    product=product.identity.normalized_name,
                    specification=product.specification.model_dump_json(),
                )
                lookup = self.cache.lookup(key)
                cache_events.append(
                    CacheEvent(
                        hit=lookup.hit,
                        age_seconds=lookup.age_seconds,
                        platform_id=adapter.platform_id,
                        source_store=store,
                        normalized_product=product.identity.normalized_name,
                        specification=product.specification.model_dump_json(),
                    )
                )
                if lookup.offer is not None:
                    offer = lookup.offer
                    cache_hits += 1
                else:
                    cache_misses += 1
                    normalized = adapter.normalize_product(product)
                    final_price = self._final_price(
                        normalized.base_price.amount if normalized.base_price else None,
                        product.promotions,
                        effective_amount=normalized.effective_price.amount if normalized.effective_price else None,
                    )
                    offer = NormalizedOffer(
                        platform_id=adapter.platform_id,
                        source_store=store,
                        candidate_id=product.node_id,
                        identity=product.identity,
                        specification=normalized.specification,
                        promotions=product.promotions,
                        final_price=final_price,
                        quantity=normalized.quantity,
                        effective_unit_price=self._effective_unit_price(
                            final_price.amount,
                            normalized.quantity,
                        ),
                        confidence=normalized.confidence,
                        extraction_source=normalized.extraction_source,
                    )
                    self.cache.set(key, offer)
                comparable, reason = self.matcher.match(requirement, offer)
                offers.append(offer.model_copy(update={"comparable": comparable, "match_reason": reason}))

        comparable_offers = [
            offer
            for offer in offers
            if offer.comparable
            and offer.final_price.amount is not None
            and offer.effective_unit_price is not None
        ]
        if len(comparable_offers) < 2:
            return ComparisonResult(
                requirement=requirement,
                offers=offers,
                comparable=False,
                reason="fewer than two comparable platform offers; no forced recommendation",
                comparison_confidence=0.0,
                comparison_reason="NEED_MORE_EVIDENCE: fewer than two offers have resolved comparable pricing",
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                cache_events=cache_events,
            )
        recommended = min(
            comparable_offers,
            key=lambda offer: (
                offer.effective_unit_price or Decimal("Infinity"),
                -offer.confidence,
            ),
        )
        return ComparisonResult(
            requirement=requirement,
            offers=offers,
            comparable=True,
            recommended_platform=recommended.platform_id,
            reason="comparable offers matched by normalized identity and specification",
            comparison_confidence=min(offer.confidence for offer in comparable_offers),
            comparison_reason="RESOLVED: identity, specification, quantity and price evidence are comparable",
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            cache_events=cache_events,
        )

    @staticmethod
    def _final_price(
        listed_amount: Decimal | None,
        promotions,
        *,
        effective_amount: Decimal | None = None,
    ) -> FinalPrice:
        if listed_amount is None:
            return FinalPrice(
                listed_amount=None,
                amount=None,
                calculation_note="price unavailable",
                pricing_status="UNRESOLVED",
            )
        if effective_amount is not None:
            return FinalPrice(
                listed_amount=listed_amount,
                amount=effective_amount,
                calculation_note="explicitly evidenced effective price",
                pricing_status=PricingStatus.RESOLVED,
            )
        rules: list[PricingRule] = []
        for promotion in promotions:
            if promotion.discount_amount is None and promotion.discount_ratio is None:
                continue
            if promotion.kind is PromotionType.SECOND_ITEM_DISCOUNT:
                rule_type = PricingRuleType.MULTI_ITEM
            elif promotion.kind is PromotionType.COUPON:
                rule_type = PricingRuleType.COUPON
            else:
                rule_type = PricingRuleType.DIRECT_DISCOUNT
            condition_confirmed = promotion.threshold_amount is None or (
                promotion.threshold_amount is not None and listed_amount >= promotion.threshold_amount
            )
            rules.append(
                PricingRule(
                    rule_type=rule_type,
                    amount=promotion.discount_amount,
                    ratio=promotion.discount_ratio,
                    threshold_amount=promotion.threshold_amount,
                    condition_confirmed=condition_confirmed,
                    evidence=promotion.raw_text,
                )
            )
        result = PricingEngine().calculate(listed_amount, rules, order_subtotal=listed_amount)
        if result.status is PricingStatus.UNRESOLVED:
            return FinalPrice(
                listed_amount=listed_amount,
                amount=None,
                calculation_note=result.reason,
                pricing_status="UNRESOLVED",
            )
        return FinalPrice(
            listed_amount=listed_amount,
            discount_amount=result.discount_amount,
            amount=result.effective_price,
            calculation_note=result.reason,
            pricing_status=PriceResolutionStatus.RESOLVED,
        )

    @staticmethod
    def _effective_unit_price(amount: Decimal | None, quantity) -> Decimal | None:
        """Return price per normalized content unit, never a display-price rank."""

        if amount is None or quantity is None:
            return None
        total_content = None
        if quantity.normalized_content_amount is not None:
            total_content = quantity.normalized_content_amount * quantity.count
        elif quantity.count:
            total_content = Decimal(quantity.count)
        if total_content is None or total_content <= 0:
            return None
        return amount / total_content
