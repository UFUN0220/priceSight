"""Cross-platform normalized offer comparison with conservative cache use."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from app.cache.offer import OfferCache
from app.comparison.matcher import ProductMatcher
from app.comparison.models import CacheEvent, ComparisonResult, FinalPrice, NormalizedOffer
from app.observation.models import Observation
from app.platform.base import PlatformAdapter


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
            extraction = adapter.extract_products(observation)
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
                    offer = NormalizedOffer(
                        platform_id=adapter.platform_id,
                        source_store=store,
                        candidate_id=product.node_id,
                        identity=product.identity,
                        specification=product.specification,
                        promotions=product.promotions,
                        final_price=self._final_price(product.price.amount if product.price else None, product.promotions),
                    )
                    self.cache.set(key, offer)
                comparable, reason = self.matcher.match(requirement, offer)
                offers.append(offer.model_copy(update={"comparable": comparable, "match_reason": reason}))

        comparable_offers = [offer for offer in offers if offer.comparable and offer.final_price.amount is not None]
        if len(comparable_offers) < 2:
            return ComparisonResult(
                requirement=requirement,
                offers=offers,
                comparable=False,
                reason="fewer than two comparable platform offers; no forced recommendation",
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                cache_events=cache_events,
            )
        recommended = min(comparable_offers, key=lambda offer: offer.final_price.amount or Decimal("Infinity"))
        return ComparisonResult(
            requirement=requirement,
            offers=offers,
            comparable=True,
            recommended_platform=recommended.platform_id,
            reason="comparable offers matched by normalized identity and specification",
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            cache_events=cache_events,
        )

    @staticmethod
    def _final_price(amount: Decimal | None, promotions) -> FinalPrice:
        if amount is None:
            return FinalPrice(listed_amount=None, amount=None, calculation_note="price unavailable")
        discount = sum(
            (promotion.discount_amount or Decimal("0"))
            for promotion in promotions
            if promotion.discount_amount is not None
        )
        final = max(Decimal("0.01"), amount - discount)
        return FinalPrice(
            listed_amount=amount,
            discount_amount=discount,
            amount=final,
            calculation_note="listed price minus explicitly parsed coupon/promotion discounts",
        )
