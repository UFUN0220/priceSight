"""Meituan adapter for controlled, sanitized observations.

This is a fixture/contract adapter, not a live Meituan integration. It uses
the same observation and normalized-product contract as the other adapters.
"""

from app.platform.fixture.adapter import FixtureOfferAdapter
from app.platform.models import NormalizedProduct, PlatformProduct


class MeituanPlatformAdapter(FixtureOfferAdapter):
    """Offline Meituan adapter used to validate multi-platform extensibility."""

    def __init__(self) -> None:
        super().__init__("meituan", "com.pricesight.fixture.meituan")

    def normalize_product(self, product: PlatformProduct) -> NormalizedProduct:
        normalized = super().normalize_product(product)
        return normalized.model_copy(update={"extraction_source": "meituan_fixture"})
