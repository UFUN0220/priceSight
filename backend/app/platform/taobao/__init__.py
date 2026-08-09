"""Taobao-specific browser adapter boundary."""

from app.platform.taobao.adapter import TaobaoPlatformAdapter
from app.platform.taobao.models import (
    TAOBAO_ALLOWED_HOSTS,
    TaobaoProductFixture,
    TaobaoPageAssessment,
    TaobaoPageState,
    TaobaoStructuredPageFixture,
    TaobaoSearchFixture,
    TaobaoSelectorConfig,
)

__all__ = [
    "TAOBAO_ALLOWED_HOSTS",
    "TaobaoPlatformAdapter",
    "TaobaoProductFixture",
    "TaobaoPageAssessment",
    "TaobaoPageState",
    "TaobaoSearchFixture",
    "TaobaoStructuredPageFixture",
    "TaobaoSelectorConfig",
]
