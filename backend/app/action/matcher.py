"""Deterministic action target matching against one fresh observation."""

from __future__ import annotations

from difflib import SequenceMatcher
from enum import StrEnum

from pydantic import BaseModel, Field

from app.action.models import ActionTarget
from app.observation.models import Observation, ObservationNode


class MatchStrategy(StrEnum):
    RESOURCE_ID = "RESOURCE_ID"
    NODE_ID = "NODE_ID"
    EXACT_TEXT = "EXACT_TEXT"
    NORMALIZED_TEXT = "NORMALIZED_TEXT"
    FUZZY_TEXT = "FUZZY_TEXT"
    COORDINATE_FALLBACK = "COORDINATE_FALLBACK"


class TargetMatch(BaseModel):
    found: bool = False
    ambiguous: bool = False
    node_id: str | None = None
    bounds: tuple[int, int, int, int] | None = None
    strategy: MatchStrategy | None = None
    score: float = 0.0
    candidates: list[str] = Field(default_factory=list)
    reason: str | None = None


class TargetMatcher:
    """Resolve targets by stable identity before semantic or coordinate fallbacks."""

    def __init__(self, fuzzy_threshold: float = 0.72) -> None:
        self.fuzzy_threshold = fuzzy_threshold

    def match(self, target: ActionTarget | None, observation: Observation) -> TargetMatch:
        if target is None:
            return TargetMatch(reason="action does not require a target")

        nodes = observation.nodes
        if target.resource_id:
            result = self._unique(
                [node for node in nodes if node.resource_id == target.resource_id],
                MatchStrategy.RESOURCE_ID,
            )
            if result is not None:
                return result

        if target.node_id:
            result = self._unique(
                [node for node in nodes if node.node_id == target.node_id],
                MatchStrategy.NODE_ID,
            )
            if result is not None:
                return result

        exact_queries = [query for query in (target.text, target.content_description) if query]
        if exact_queries:
            exact_nodes = [
                node
                for node in nodes
                if any(query == value for query in exact_queries for value in self._values(node))
            ]
            result = self._unique(exact_nodes, MatchStrategy.EXACT_TEXT)
            if result is not None:
                return result

        normalized_queries = [
            self._normalize(query)
            for query in (target.text, target.content_description, target.semantic_hint)
            if query
        ]
        if normalized_queries:
            normalized_nodes = [
                node
                for node in nodes
                if any(
                    query == self._normalize(value)
                    for query in normalized_queries
                    for value in self._values(node)
                )
            ]
            result = self._unique(normalized_nodes, MatchStrategy.NORMALIZED_TEXT)
            if result is not None:
                return result

            fuzzy = self._fuzzy(normalized_queries, nodes)
            if fuzzy is not None:
                return fuzzy

        if target.bounds is not None:
            result = self._unique(
                [node for node in nodes if node.bounds == target.bounds],
                MatchStrategy.COORDINATE_FALLBACK,
            )
            if result is not None:
                return result

        return TargetMatch(reason="target not found in fresh observation")

    def _fuzzy(self, queries: list[str], nodes: list[ObservationNode]) -> TargetMatch | None:
        scored: list[tuple[float, ObservationNode]] = []
        for node in nodes:
            values = [self._normalize(value) for value in self._values(node)]
            if not values:
                continue
            score = max(SequenceMatcher(None, query, value).ratio() for query in queries for value in values)
            if score >= self.fuzzy_threshold:
                scored.append((score, node))
        if not scored:
            return None
        scored.sort(key=lambda item: (-item[0], item[1].node_id))
        best_score = scored[0][0]
        best = [node for score, node in scored if best_score - score < 0.03]
        if len(best) != 1:
            return TargetMatch(
                ambiguous=True,
                strategy=MatchStrategy.FUZZY_TEXT,
                score=best_score,
                candidates=[node.node_id for node in best],
                reason="fuzzy candidates are ambiguous",
            )
        return self._found(best[0], MatchStrategy.FUZZY_TEXT, best_score)

    @staticmethod
    def _unique(nodes: list[ObservationNode], strategy: MatchStrategy) -> TargetMatch | None:
        if not nodes:
            return None
        if len(nodes) != 1:
            return TargetMatch(
                ambiguous=True,
                strategy=strategy,
                candidates=[node.node_id for node in nodes],
                reason="multiple candidates matched",
            )
        return TargetMatcher._found(nodes[0], strategy, 1.0)

    @staticmethod
    def _found(node: ObservationNode, strategy: MatchStrategy, score: float) -> TargetMatch:
        return TargetMatch(
            found=True,
            node_id=node.node_id,
            bounds=node.bounds,
            strategy=strategy,
            score=score,
        )

    @staticmethod
    def _values(node: ObservationNode) -> list[str]:
        return [
            value
            for value in (node.text, node.content_description, node.resource_id, node.class_name)
            if value
        ]

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())

