"""Structured product, quantity, specification, and parse-result models."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Unit(StrEnum):
    ML = "ml"
    L = "l"
    G = "g"
    KG = "kg"
    PIECE = "piece"
    PACK = "pack"
    BOTTLE = "bottle"
    CAN = "can"
    BAG = "bag"
    CUP = "cup"
    BOX = "box"
    CASE = "case"
    UNKNOWN = "unknown"


class ParseSource(StrEnum):
    RULE = "rule"
    LLM = "llm"
    RULE_FALLBACK = "rule_fallback"


class ParserSource(StrEnum):
    """Provenance of the complete parser pipeline."""

    RULE = "RULE"
    LLM = "LLM"
    HYBRID = "HYBRID"


class ProductIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_text: str
    name: str
    normalized_name: str
    brand: str | None = None


class Quantity(BaseModel):
    """One package quantity, preserving both content and package count."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str
    count: int = Field(default=1, ge=1)
    content_amount: Decimal | None = Field(default=None, gt=0)
    content_unit: Unit | None = None
    container_unit: Unit | None = None
    normalized_content_amount: Decimal | None = Field(default=None, gt=0)
    normalized_content_unit: Unit | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PromotionType(StrEnum):
    BUY_GET = "buy_get"
    GIFT = "gift"
    COMBO = "combo"
    COUPON = "coupon"
    OTHER = "other"


class Promotion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    kind: PromotionType
    buy_count: int | None = Field(default=None, ge=1)
    gift_count: int | None = Field(default=None, ge=1)
    gift_quantity: Quantity | None = None
    threshold_amount: Decimal | None = Field(default=None, gt=0)
    discount_amount: Decimal | None = Field(default=None, gt=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ProductSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_text: str
    primary_quantity: Quantity | None = None
    components: list[Quantity] = Field(default_factory=list)
    package_type: str | None = None
    ambiguous: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_text: str
    normalized_text: str
    product_identity: ProductIdentity
    specification: ProductSpecification
    promotions: list[Promotion] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguous: bool = False
    source: ParseSource = ParseSource.RULE
    parser_source: ParserSource = ParserSource.RULE
    candidate_count: int = Field(default=0, ge=0)
    reason_code: str = "deterministic_confident"
    reason: str | None = None
    llm_fallback_attempted: bool = False
    llm_schema_valid: bool | None = None
    llm_invocation_reason: str | None = None
    fallback_reason: str | None = None


class LLMParseSuggestion(BaseModel):
    """Strict JSON schema accepted from an LLM fallback."""

    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(min_length=1)
    normalized_product_name: str = Field(min_length=1)
    quantity: Quantity | None = None
    promotions: list[Promotion] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reason_summary: str = Field(min_length=1)
    reason_code: str = Field(default="llm_structured_resolution", min_length=1)
