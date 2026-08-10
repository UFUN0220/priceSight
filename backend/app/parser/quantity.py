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
        r"(?P<unit>GB|TB|mm|cm|inch|英寸|寸|毫升|ml|升|l|千克|kg|公斤|克|g|m)\s*"
        r"(?:x\s*(?P<count>\d+)|(?P<count_after>\d+)\s*(?P<container_after>瓶|罐|袋|杯|盒|箱|包|件))?\s*"
        r"(?P<container>瓶|罐|袋|杯|盒|箱|包|件)?(?![A-Za-z])",
        re.IGNORECASE,
    )
    _measure_with_prefix = re.compile(
        r"(?P<count_before>\d+|一|二|两|三|四|五|六|七|八|九|十)\s*"
        r"(?P<container_before>瓶|罐|袋|杯|盒|箱|包|件|双|卷)\s+"
        r"(?P<amount>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>GB|TB|mm|cm|inch|英寸|寸|毫升|ml|升|l|千克|kg|公斤|克|g|m)(?![A-Za-z])",
        re.IGNORECASE,
    )
    _count_only = re.compile(
        r"(?P<count>\d+|一|二|两|三|四|五|六|七|八|九|十)\s*"
        r"(?P<unit>瓶|罐|袋|杯|盒|箱|包|件|个|支|双|卷|张)\s*(?:装)?"
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
        "gb": Unit.GB,
        "tb": Unit.TB,
        "mm": Unit.MM,
        "cm": Unit.CM,
        "inch": Unit.INCH,
        "英寸": Unit.INCH,
        "寸": Unit.INCH,
        "m": Unit.M,
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
        "双": Unit.PAIR,
        "卷": Unit.ROLL,
        "张": Unit.SHEET,
    }
    _count_words = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

    @staticmethod
    def normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text)
        normalized = normalized.replace("×", "x").replace("*", "x")
        return " ".join(normalized.split())

    def parse_first(self, text: str) -> QuantityMatch | None:
        normalized = self.normalize(text)
        measure = self._measure.search(normalized)
        prefixed_measure = self._measure_with_prefix.search(normalized)
        count_only = self._count_only.search(normalized)
        if prefixed_measure is not None and (measure is None or prefixed_measure.start() <= measure.start()):
            measure = prefixed_measure
        if measure is not None and (count_only is None or measure.start() <= count_only.start()):
            return self._from_measure(measure)
        if count_only is not None:
            return self._from_count_only(count_only)
        return None

    def parse_all(self, text: str) -> list[QuantityMatch]:
        normalized = self.normalize(text)
        matches: list[QuantityMatch] = []
        occupied_until = -1
        all_measure_matches = [*self._measure.finditer(normalized), *self._measure_with_prefix.finditer(normalized)]
        for match in sorted(all_measure_matches, key=lambda item: item.start()):
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
        groups = match.groupdict()
        amount = Decimal(match.group("amount"))
        unit = self._units[match.group("unit").casefold()]
        count_text = groups.get("count_before") or groups.get("count") or groups.get("count_after") or "1"
        count = self._count_words.get(count_text, int(count_text) if count_text.isdigit() else 1)
        container_key = groups.get("container_before") or groups.get("container") or groups.get("container_after") or ""
        container = self._containers.get(container_key)
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
                confidence=0.98 if (groups.get("count_before") or groups.get("count") or groups.get("count_after")) else 0.94,
            ),
            start=match.start(),
            end=match.end(),
        )

    def _from_count_only(self, match: re.Match[str]) -> QuantityMatch:
        unit = self._containers[match.group("unit")]
        package_only = unit in {Unit.PAIR, Unit.ROLL, Unit.SHEET}
        return QuantityMatch(
            quantity=Quantity(
                raw_text=match.group(0).strip(),
                count=self._count_words.get(match.group("count"), int(match.group("count")) if match.group("count").isdigit() else 1),
                content_unit=None if package_only else unit,
                container_unit=unit if package_only else None,
                normalized_content_unit=None if package_only else unit,
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

    @staticmethod
    def is_product_quantity(quantity: Quantity) -> bool:
        """Digital and dimensional values describe a SKU, not purchase count."""

        return quantity.content_unit not in {
            Unit.GB,
            Unit.TB,
            Unit.MM,
            Unit.CM,
            Unit.M,
            Unit.INCH,
        }
