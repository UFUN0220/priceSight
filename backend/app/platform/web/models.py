"""Configuration and evidence models for browser-backed platform adapters."""

from pydantic import BaseModel, ConfigDict, Field


class WebSelectorConfig(BaseModel):
    """Stable semantic/resource contracts extracted by BrowserRuntime."""

    model_config = ConfigDict(extra="forbid")

    product_result_resource_prefix: str = "product-result"
    product_result_content_description: str = "product_result"
    product_title_resource_id: str = "product-title"
    price_resource_id: str = "product-price"
    promotion_resource_id: str = "product-promotion"
    search_resource_id: str = "search-button"
    search_input_resource_id: str = "search-input"
    search_submit_resource_id: str = "search-submit"
    checkout_resource_id: str = "checkout"
    add_to_cart_resource_id: str = "add-to-cart"


class WebEvidence(BaseModel):
    """Sanitized evidence metadata attached to a read-only extraction."""

    model_config = ConfigDict(extra="forbid")

    platform_id: str
    page_type: str
    source_url: str | None = None
    title: str | None = None
    observation_id: str
    captured_at: str | None = None
    node_ids: list[str] = Field(default_factory=list)
