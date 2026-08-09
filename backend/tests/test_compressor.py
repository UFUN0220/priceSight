"""Regression tests for deterministic observation compression."""

from pathlib import Path

from app.observation.compressor import ObservationCompressor
from app.observation.models import Observation


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "observations"


def load_fixture(name: str) -> Observation:
    return Observation.model_validate_json((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def compress(name: str):
    return ObservationCompressor().compress(load_fixture(name))


def test_normal_product_list_removes_layout_and_keeps_content() -> None:
    result = compress("normal_product_list.json")
    node_ids = {node.node_id for node in result.observation.nodes}

    assert result.stats.raw_node_count == 10
    assert result.stats.compressed_node_count < result.stats.raw_node_count
    assert {"search", "name-a", "price-a", "name-b", "price-b"} <= node_ids
    assert "decorative" not in node_ids
    assert result.stats.raw_serialized_chars > result.stats.compressed_serialized_chars


def test_empty_nodes_are_pruned_but_interactive_nodes_survive() -> None:
    result = compress("empty_nodes.json")
    node_ids = {node.node_id for node in result.observation.nodes}

    assert node_ids == {"button", "editor"}
    assert all(node.action_priority > 0 for node in result.observation.nodes)


def test_nested_layout_is_flattened_without_losing_leaf() -> None:
    result = compress("nested_layout.json")
    node_ids = {node.node_id for node in result.observation.nodes}

    assert "label" in node_ids
    assert "scroll" in node_ids
    assert "layout-a" not in node_ids
    assert "layout-b" not in node_ids


def test_empty_clickable_and_scrollable_nodes_are_preserved() -> None:
    result = compress("clickable_empty.json")
    node_ids = {node.node_id for node in result.observation.nodes}

    assert node_ids == {"button", "scroll"}
    assert result.observation.nodes[0].action_priority >= 80


def test_duplicate_product_cards_are_not_collapsed_into_one_card() -> None:
    result = compress("duplicate_product_cards.json")
    node_ids = {node.node_id for node in result.observation.nodes}

    assert {"title-a", "price-a", "title-b", "price-b"} <= node_ids


def test_empty_observation_is_safe_and_measurable() -> None:
    result = compress("no_root.json")

    assert result.observation.nodes == []
    assert result.stats.raw_node_count == 0
    assert result.stats.compressed_node_count == 0
    assert result.stats.compression_ratio == 0.0

