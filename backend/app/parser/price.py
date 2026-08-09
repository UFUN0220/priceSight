"""Reserved price parsing boundary for the next comparison phase."""

from decimal import Decimal
import re

from pydantic import BaseModel, ConfigDict, Field


class Price(BaseModel):
    """Minimal typed price DTO; promotion arithmetic is intentionally deferred."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0)
    currency: str = "CNY"
    original_text: str


class PriceParser:
    """Deterministic price extraction for platform adapters."""

    _pattern = re.compile(r"(?:¥|￥|人民币|RMB)\s*(\d+(?:\.\d{1,2})?)")

    def parse(self, text: str) -> Price | None:
        match = self._pattern.search(text)
        if match is None:
            return None
        return Price(amount=Decimal(match.group(1)), original_text=match.group(0))
