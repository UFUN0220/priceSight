"""Comparable cross-platform offer models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.parser.models import ProductIdentity, ProductSpecification, Promotion, Quantity


class NormalizedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    identity: ProductIdentity
    specification: ProductSpecification


class FinalPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listed_amount: Decimal | None = Field(default=None, gt=0)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str = "CNY"
    calculation_note: str | None = None


class NormalizedOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_id: str
    source_store: str
    candidate_id: str
    identity: ProductIdentity
    specification: ProductSpecification
    promotions: list[Promotion] = Field(default_factory=list)
    final_price: FinalPrice
    quantity: Quantity | None = None
    effective_unit_price: Decimal | None = Field(default=None, gt=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_source: str = "unknown"
    comparable: bool = False
    match_reason: str | None = None


class CacheEvent(BaseModel):
    """Measured cache lookup metadata for comparison reports."""

    hit: bool
    age_seconds: float | None = Field(default=None, ge=0)
    platform_id: str
    source_store: str
    normalized_product: str
    specification: str


class ComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: NormalizedRequirement
    offers: list[NormalizedOffer] = Field(default_factory=list)
    comparable: bool
    recommended_platform: str | None = None
    reason: str
    cache_hits: int = 0
    cache_misses: int = 0
    cache_events: list[CacheEvent] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
