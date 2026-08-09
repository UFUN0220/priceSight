"""JD adapter for controlled, sanitized observations.

This is a fixture/contract adapter, not a live JD integration. It reuses the
shared mock observation contract so the comparison layer does not know about
JD selectors or transport details.
"""

from app.platform.fixture.adapter import FixtureOfferAdapter
from app.platform.models import NormalizedProduct, PlatformProduct


class JdPlatformAdapter(FixtureOfferAdapter):
    """Offline JD adapter used to validate multi-platform extensibility."""

    def __init__(self) -> None:
        super().__init__("jd", "com.pricesight.fixture.jd")

    def normalize_product(self, product: PlatformProduct) -> NormalizedProduct:
        normalized = super().normalize_product(product)
        return normalized.model_copy(update={"extraction_source": "jd_fixture"})
