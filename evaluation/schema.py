"""Versioned, annotation-aware schemas for evaluation datasets."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceType(StrEnum):
    SYNTHETIC = "synthetic"
    FIXTURE = "fixture"
    REAL_ANONYMIZED = "real_anonymized"


class AnnotationStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    MACHINE_DRAFT = "MACHINE_DRAFT"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    REJECTED = "REJECTED"


class AmbiguityType(StrEnum):
    NONE = "none"
    MULTI_PACK = "multi_pack"
    MULTI_SPEC = "multi_spec"
    SECOND_ITEM_DISCOUNT = "second_item_discount"
    AFTER_SALE_PRICE = "after_sale_price"
    COUPON_PRICE = "coupon_price"
    PRICE_RANGE = "price_range"
    GIFT = "gift"
    SKU_MIXED_TEXT = "sku_mixed_text"
    QUANTITY_AMBIGUITY = "quantity_ambiguity"
    UNIT_AMBIGUITY = "unit_ambiguity"
    TITLE_NOISE = "title_noise"
    MISSING_INFORMATION = "missing_information"
    DUPLICATE_NODE = "duplicate_node"
    POPUP_LOADING = "popup_loading"
    DYNAMIC_PRICE = "dynamic_price"


class ExpectedQuantity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int | None = Field(default=None, ge=1)
    content_amount: Decimal | None = Field(default=None, gt=0)
    content_unit: str | None = None
    container_unit: str | None = None


class ExpectedSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_type: str | None = None
    notes: str | None = None


class ExpectedPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0)
    currency: str = "CNY"
    price_kind: str = "displayed"


class ParsedOutput(BaseModel):
    """Comparable parser output; this is not an annotation."""

    model_config = ConfigDict(extra="forbid")

    product_name: str | None = None
    quantity: ExpectedQuantity | None = None
    spec: ExpectedSpecification | None = None
    price: ExpectedPrice | None = None
    source: str | None = None
    ambiguous: bool | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class EvaluationSample(BaseModel):
    """One replayable sample with explicit provenance and annotation state."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    source_type: SourceType
    query: str = Field(min_length=1)
    raw_observation: dict[str, Any] | None = None
    fixture_reference: str | None = None
    expected_quantity: ExpectedQuantity | None = None
    expected_spec: ExpectedSpecification | None = None
    expected_price: ExpectedPrice | None = None
    expected_product_name: str | None = None
    ambiguity_type: AmbiguityType = AmbiguityType.NONE
    annotation_status: AnnotationStatus = AnnotationStatus.UNREVIEWED
    parser_output: ParsedOutput | None = None
    model_output: ParsedOutput | None = None
    final_output: ParsedOutput | None = None
    success: bool | None = None
    failure_reason: str | None = None

    @model_validator(mode="after")
    def require_replay_source(self) -> "EvaluationSample":
        if self.raw_observation is None and not self.fixture_reference:
            raise ValueError("sample must include raw_observation or fixture_reference")
        if self.annotation_status is AnnotationStatus.HUMAN_VERIFIED and self.source_type is SourceType.SYNTHETIC:
            raise ValueError("synthetic samples cannot be HUMAN_VERIFIED without a human annotation record")
        return self


def load_sample(line: str) -> EvaluationSample:
    """Validate one JSONL line and fail closed on unknown fields."""

    return EvaluationSample.model_validate_json(line)
