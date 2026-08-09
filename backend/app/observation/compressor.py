"""Deterministic Accessibility observation compression pipeline."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter

from pydantic import BaseModel

from app.observation.models import Observation, ObservationNode
from app.observation.serializer import serialize_observation


class CompressionStats(BaseModel):
    """Measured statistics for one compression run.

    ``compression_ratio`` is the retained-node ratio:
    ``compressed_node_count / raw_node_count``. A lower value means more
    nodes were removed. It is intentionally not presented as a performance
    claim; it describes only the supplied fixture.
    """

    raw_node_count: int
    compressed_node_count: int
    compression_ratio: float
    raw_serialized_chars: int
    compressed_serialized_chars: int
    processing_latency_ms: float


class CompressionResult(BaseModel):
    """Compressed observation plus auditable run statistics."""

    observation: Observation
    stats: CompressionStats


@dataclass
class _Tree:
    nodes: dict[str, ObservationNode]
    children: dict[str, list[str]]
    roots: list[str]


class ObservationCompressor:
    """Run normalization, pruning, conservative merging, and prioritization."""

    def compress(self, observation: Observation) -> CompressionResult:
        started = perf_counter()
        raw_json = serialize_observation(observation)
        normalized = self._normalize(observation)
        tree = self._build_tree(normalized)
        roots = self._compress_tree(tree)
        self._merge_duplicate_leaves(tree, roots)
        compressed = self._materialize(normalized, tree, roots)
        compressed_json = serialize_observation(compressed)

        raw_count = len(observation.nodes)
        compressed_count = len(compressed.nodes)
        stats = CompressionStats(
            raw_node_count=raw_count,
            compressed_node_count=compressed_count,
            compression_ratio=(compressed_count / raw_count) if raw_count else 0.0,
            raw_serialized_chars=len(raw_json),
            compressed_serialized_chars=len(compressed_json),
            processing_latency_ms=(perf_counter() - started) * 1000,
        )
        return CompressionResult(observation=compressed, stats=stats)

    def _normalize(self, observation: Observation) -> Observation:
        normalized_nodes: list[ObservationNode] = []
        seen_ids: set[str] = set()
        for node in observation.nodes:
            if node.node_id in seen_ids:
                continue
            seen_ids.add(node.node_id)
            normalized_nodes.append(
                node.model_copy(
                    update={
                        "class_name": self._clean(node.class_name),
                        "text": self._clean(node.text),
                        "content_description": self._clean(node.content_description),
                        "resource_id": self._clean(node.resource_id),
                    }
                )
            )
        return observation.model_copy(update={"nodes": normalized_nodes})

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    def _build_tree(self, observation: Observation) -> _Tree:
        nodes = {node.node_id: node for node in observation.nodes}
        children: dict[str, list[str]] = defaultdict(list)

        for node in observation.nodes:
            if node.parent_id in nodes and node.node_id not in children[node.parent_id]:
                children[node.parent_id].append(node.node_id)

        for node in observation.nodes:
            for child_id in node.children:
                if child_id in nodes and child_id not in children[node.node_id]:
                    children[node.node_id].append(child_id)

        attached = {child_id for child_ids in children.values() for child_id in child_ids}
        roots = [node.node_id for node in observation.nodes if node.node_id not in attached]
        return _Tree(nodes=nodes, children=dict(children), roots=roots)

    def _compress_tree(self, tree: _Tree) -> list[str]:
        visited: set[str] = set()

        def compress_node(node_id: str, is_root: bool = False) -> list[str]:
            if node_id in visited or node_id not in tree.nodes:
                return []
            visited.add(node_id)
            node = tree.nodes[node_id]
            retained_children: list[str] = []
            for child_id in tree.children.get(node_id, []):
                retained_children.extend(compress_node(child_id))
            tree.children[node_id] = retained_children

            interactive = self._is_interactive(node)
            semantic = self._has_semantics(node)
            visible = node.visible

            # Invisible non-interactive nodes are removed, but retained
            # descendants are promoted so useful content is not lost.
            if not visible and not interactive:
                return retained_children
            # Empty structural nodes never survive without useful descendants.
            if not semantic and not interactive and not retained_children:
                return []
            # A single-child layout wrapper is redundant. Multi-child
            # containers are retained because they may represent a product
            # card or another semantic grouping even without container text.
            if not semantic and not interactive:
                if is_root:
                    return retained_children
                if len(retained_children) == 1:
                    return retained_children
                if retained_children:
                    return [node_id]
                return []
            return [node_id]

        roots: list[str] = []
        for root_id in tree.roots:
            roots.extend(compress_node(root_id, is_root=True))
        # Malformed or cyclic fixtures should still yield deterministic output.
        for node_id in tree.nodes:
            if node_id not in visited:
                roots.extend(compress_node(node_id))
        return roots

    def _merge_duplicate_leaves(self, tree: _Tree, roots: list[str]) -> None:
        removed: set[str] = set()

        def signature(node: ObservationNode) -> tuple[object, ...]:
            return (
                node.class_name,
                node.text,
                node.content_description,
                node.resource_id,
                node.clickable,
                node.editable,
                node.scrollable,
            )

        def process_siblings(sibling_ids: list[str]) -> list[str]:
            result: list[str] = []
            seen_siblings: dict[tuple[object, ...], str] = {}
            for node_id in sibling_ids:
                if node_id not in tree.nodes or node_id in removed:
                    continue
                child_ids = tree.children.get(node_id, [])
                if not child_ids:
                    node = tree.nodes[node_id]
                    if not self._is_interactive(node):
                        key = signature(node)
                        if key in seen_siblings:
                            removed.add(node_id)
                            continue
                        seen_siblings[key] = node_id
                tree.children[node_id] = process_siblings(child_ids)
                result.append(node_id)
            return result

        roots[:] = process_siblings(roots)
        for node_id in removed:
            tree.nodes.pop(node_id, None)
            tree.children.pop(node_id, None)

    def _materialize(self, observation: Observation, tree: _Tree, roots: list[str]) -> Observation:
        ordered: list[ObservationNode] = []
        visited: set[str] = set()

        def visit(node_id: str, parent_id: str | None, depth: int) -> None:
            if node_id in visited or node_id not in tree.nodes:
                return
            visited.add(node_id)
            node = tree.nodes[node_id]
            child_ids = [child_id for child_id in tree.children.get(node_id, []) if child_id in tree.nodes]
            ordered.append(
                node.model_copy(
                    update={
                        "parent_id": parent_id,
                        "children": child_ids,
                        "depth": depth,
                        "action_priority": self._action_priority(node),
                    }
                )
            )
            for child_id in child_ids:
                visit(child_id, node_id, depth + 1)

        for root_id in roots:
            visit(root_id, None, 0)
        return observation.model_copy(update={"nodes": ordered})

    @staticmethod
    def _has_semantics(node: ObservationNode) -> bool:
        return any((node.text, node.content_description, node.resource_id))

    @staticmethod
    def _is_interactive(node: ObservationNode) -> bool:
        return node.clickable or node.editable or node.scrollable

    @staticmethod
    def _action_priority(node: ObservationNode) -> int:
        if node.editable:
            return 100
        if node.clickable:
            return 90
        if node.scrollable:
            return 80
        if node.text or node.content_description or node.resource_id:
            return 10
        return 0
