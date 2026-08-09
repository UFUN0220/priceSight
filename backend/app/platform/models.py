"""Platform-neutral adapter DTOs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.action.models import ActionTarget
from app.parser.models import ProductIdentity, ProductSpecification, Promotion, Quantity
from app.parser.price import Price


class PlatformPageType(StrEnum):
    UNKNOWN = "unknown"
    HOME = "home"
    SEARCH = "search"
    RESULTS = "results"
    PRODUCT = "product"
    CART = "cart"
    ORDER_CONFIRM = "order_confirm"
    PAYMENT = "payment"


class PlatformProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    raw_title: str
    identity: ProductIdentity
    specification: ProductSpecification
    price: Price | None = None
    displayed_price: Price | None = None
    original_price: Price | None = None
    product_url: str | None = None
    product_id: str | None = None
    seller: str | None = None
    sales_info: str | None = None
    observation_id: str | None = None
    extraction_source: str = "observation"
    selector_strategy: str | None = None
    selector_fallback_level: int | None = Field(default=None, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    promotions: list[Promotion] = Field(default_factory=list)


class NormalizedProduct(BaseModel):
    """Platform-neutral product contract used by comparison and agent layers.

    ``base_price`` is the original/listed price when the adapter can identify
    one. ``effective_price`` is the price after only explicitly parsed
    promotions. Both fields preserve the typed ``Price`` value and its source
    text so downstream code cannot mistake a fixture for live platform data.
    """

    model_config = ConfigDict(extra="forbid")

    platform: str
    title: str
    base_price: Price | None = None
    effective_price: Price | None = None
    quantity: Quantity | None = None
    specification: ProductSpecification
    seller: str | None = None
    store: str | None = None
    product_id: str | None = None
    product_url: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_source: str


class AdapterExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recognized: bool
    platform_id: str
    page_type: PlatformPageType
    products: list[PlatformProduct] = Field(default_factory=list)
    product: PlatformProduct | None = None
    price: Price | None = None
    promotions: list[Promotion] = Field(default_factory=list)
    selector_candidates: dict[str, list[ActionTarget]] = Field(default_factory=dict)
    selector_strategy: dict[str, str] = Field(default_factory=dict)
    selector_fallback_level: dict[str, int] = Field(default_factory=dict)
    failure_reason: str | None = None


class AdapterActionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    safety_stop: bool = False
    target: ActionTarget | None = None
    failure_reason: str | None = None
