"""Taobao-specific browser adapter boundary."""

from app.platform.taobao.adapter import TaobaoPlatformAdapter
from app.platform.taobao.models import (
    TAOBAO_ALLOWED_HOSTS,
    TaobaoProductFixture,
    TaobaoStructuredPageFixture,
    TaobaoSearchFixture,
    TaobaoSelectorConfig,
)

__all__ = [
    "TAOBAO_ALLOWED_HOSTS",
    "TaobaoPlatformAdapter",
    "TaobaoProductFixture",
    "TaobaoSearchFixture",
    "TaobaoStructuredPageFixture",
    "TaobaoSelectorConfig",
]
