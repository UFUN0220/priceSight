"""Deterministic quantity and unit parsing."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from app.parser.models import Quantity, Unit


@dataclass(frozen=True)
class QuantityMatch:
    quantity: Quantity
    start: int
    end: int


class QuantityParser:
    """Parse measurable content before asking a model to interpret ambiguity."""

    _measure = re.compile(
        r"(?P<amount>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>毫升|ml|升|l|千克|kg|公斤|克|g)\s*"
        r"(?:x\s*(?P<count>\d+)|(?P<count_after>\d+)\s*(?P<container_after>瓶|罐|袋|杯|盒|箱|包|件))?\s*"
        r"(?P<container>瓶|罐|袋|杯|盒|箱|包|件)?",
        re.IGNORECASE,
    )
    _count_only = re.compile(
        r"(?P<count>\d+)\s*(?P<unit>瓶|罐|袋|杯|盒|箱|包|件|个|支)\s*(?:装)?"
    )

    _units = {
        "毫升": Unit.ML,
        "ml": Unit.ML,
        "升": Unit.L,
        "l": Unit.L,
        "千克": Unit.KG,
        "kg": Unit.KG,
        "公斤": Unit.KG,
        "克": Unit.G,
        "g": Unit.G,
    }
    _containers = {
        "瓶": Unit.BOTTLE,
        "罐": Unit.CAN,
        "袋": Unit.BAG,
        "杯": Unit.CUP,
        "盒": Unit.BOX,
        "箱": Unit.CASE,
        "包": Unit.PACK,
        "件": Unit.PIECE,
        "个": Unit.PIECE,
        "支": Unit.PIECE,
    }

    @staticmethod
    def normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text)
        normalized = normalized.replace("×", "x").replace("*", "x")
        return " ".join(normalized.split())

    def parse_first(self, text: str) -> QuantityMatch | None:
        normalized = self.normalize(text)
        measure = self._measure.search(normalized)
        count_only = self._count_only.search(normalized)
        if measure is not None and (count_only is None or measure.start() <= count_only.start()):
            return self._from_measure(measure)
        if count_only is not None:
            return self._from_count_only(count_only)
        return None

    def parse_all(self, text: str) -> list[QuantityMatch]:
        normalized = self.normalize(text)
        matches: list[QuantityMatch] = []
        occupied_until = -1
        for match in self._measure.finditer(normalized):
            if match.start() < occupied_until:
                continue
            parsed = self._from_measure(match)
            matches.append(parsed)
            occupied_until = match.end()
        for match in self._count_only.finditer(normalized):
            if match.start() < occupied_until:
                continue
            matches.append(self._from_count_only(match))
        return sorted(matches, key=lambda item: item.start)

    def _from_measure(self, match: re.Match[str]) -> QuantityMatch:
        amount = Decimal(match.group("amount"))
        unit = self._units[match.group("unit").casefold()]
        count = int(match.group("count") or match.group("count_after") or "1")
        container = self._containers.get(match.group("container") or match.group("container_after"))
        normalized_amount, normalized_unit = self._normalize_amount(amount, unit)
        return QuantityMatch(
            quantity=Quantity(
                raw_text=match.group(0).strip(),
                count=count,
                content_amount=amount,
                content_unit=unit,
                container_unit=container,
                normalized_content_amount=normalized_amount,
                normalized_content_unit=normalized_unit,
                confidence=0.98 if (match.group("count") or match.group("count_after")) else 0.94,
            ),
            start=match.start(),
            end=match.end(),
        )

    def _from_count_only(self, match: re.Match[str]) -> QuantityMatch:
        unit = self._containers[match.group("unit")]
        return QuantityMatch(
            quantity=Quantity(
                raw_text=match.group(0).strip(),
                count=int(match.group("count")),
                content_unit=unit,
                normalized_content_unit=unit,
                confidence=0.88,
            ),
            start=match.start(),
            end=match.end(),
        )

    @staticmethod
    def _normalize_amount(amount: Decimal, unit: Unit) -> tuple[Decimal, Unit]:
        if unit is Unit.L:
            return amount * Decimal("1000"), Unit.ML
        if unit is Unit.KG:
            return amount * Decimal("1000"), Unit.G
        return amount, unit
