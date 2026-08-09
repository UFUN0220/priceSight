"""Taobao adapter configuration and sanitized fixture models.

The values below are a synthetic semantic contract for fixture replay. They
are deliberately not presented as verified live-site selectors. A future
live run must replace them only after a sanitized public-page observation has
been reviewed.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.platform.web.models import WebSelectorConfig

TAOBAO_ALLOWED_HOSTS = {
    "uland.taobao.com",
    "s.taobao.com",
    "item.taobao.com",
    "www.taobao.com",
}


class TaobaoSelectorConfig(WebSelectorConfig):
    """Namespaced selector contract for Taobao fixture replay."""

    product_result_resource_prefix: str = "taobao-product-result"
    product_result_content_description: str = "taobao_product_result"
    product_title_resource_id: str = "taobao-product-title"
    price_resource_id: str = "taobao-product-price"
    promotion_resource_id: str = "taobao-product-promotion"
    search_resource_id: str = "taobao-search-button"
    search_input_resource_id: str = "taobao-search-input"
    search_submit_resource_id: str = "taobao-search-submit"
    checkout_resource_id: str = "taobao-checkout"
    add_to_cart_resource_id: str = "taobao-add-to-cart"


class TaobaoProductFixture(BaseModel):
    """One product from a reviewed, structured Taobao search fixture."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    title: str = Field(min_length=1)
    price: Decimal = Field(gt=0)
    shop_name: str = Field(min_length=1)
    shop_tag: str | None = None
    location: str | None = None
    features: list[str] = Field(default_factory=list)
    abstract: list[str] = Field(default_factory=list)


class TaobaoSearchFixture(BaseModel):
    """Structured search-page fixture; analytics and redirect links omitted."""

    model_config = ConfigDict(extra="forbid")

    source_url: str
    title: str
    query: str
    extracted_date: str
    product_list: list[TaobaoProductFixture] = Field(default_factory=list)


class TaobaoPageMetadata(BaseModel):
    """Non-sensitive page metadata retained for fixture provenance."""

    model_config = ConfigDict(extra="ignore")

    source_url: str
    title: str
    keywords: str | None = None
    extracted_date: str


class TaobaoSearchTabFixture(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str
    selected: bool = False


class TaobaoSearchBarFixture(BaseModel):
    model_config = ConfigDict(extra="ignore")

    search_query: str
    search_tabs: list[TaobaoSearchTabFixture] = Field(default_factory=list)
    search_button_label: str | None = None


class TaobaoPaginationFixture(BaseModel):
    model_config = ConfigDict(extra="ignore")

    current_page: int = Field(ge=1)
    has_next: bool = False
    has_previous: bool = False
    page_info: str | None = None


class TaobaoProductListFixture(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[TaobaoProductFixture] = Field(default_factory=list)
    pagination: TaobaoPaginationFixture | None = None


class TaobaoPageStructureFixture(BaseModel):
    """Useful page structure extracted from HTML/ARIA, without tracking data."""

    model_config = ConfigDict(extra="ignore")

    search_bar: TaobaoSearchBarFixture
    product_list: TaobaoProductListFixture


class TaobaoStructuredPageFixture(BaseModel):
    """Sanitized structured page payload supplied by the user."""

    model_config = ConfigDict(extra="ignore")

    metadata: TaobaoPageMetadata
    page_structure: TaobaoPageStructureFixture
