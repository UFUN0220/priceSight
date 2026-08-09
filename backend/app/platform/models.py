"""Platform-neutral adapter DTOs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.action.models import ActionTarget
from app.parser.models import ProductIdentity, ProductSpecification, Promotion
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
    promotions: list[Promotion] = Field(default_factory=list)


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
    failure_reason: str | None = None


class AdapterActionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    safety_stop: bool = False
    target: ActionTarget | None = None
    failure_reason: str | None = None
