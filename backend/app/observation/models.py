"""Stable backend-side observation DTOs for fake-device testing."""

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class PageType(StrEnum):
    UNKNOWN = "unknown"
    SEARCH = "search"
    PRODUCT = "product"
    CART = "cart"


class ObservationNode(BaseModel):
    """Framework-neutral node placeholder; no Android object crosses this boundary."""

    node_id: str
    parent_id: str | None = None
    class_name: str | None = None
    text: str | None = None
    content_description: str | None = None
    resource_id: str | None = None
    clickable: bool = False
    editable: bool = False
    scrollable: bool = False
    enabled: bool = True
    visible: bool = True
    bounds: tuple[int, int, int, int] | None = None
    depth: int = 0
    children: list[str] = Field(default_factory=list)
    action_priority: int = 0


class Observation(BaseModel):
    """A compact, serializable observation envelope."""

    observation_id: str
    platform: str | None = None
    package_name: str | None = None
    page_type: PageType = PageType.UNKNOWN
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timestamp_epoch_ms: int | None = None
    source_url: str | None = None
    title: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    nodes: list[ObservationNode] = Field(default_factory=list)
