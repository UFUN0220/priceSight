"""Tests for deterministic target matching priority and ambiguity handling."""

from app.action.matcher import MatchStrategy, TargetMatcher
from app.action.models import ActionTarget
from app.observation.models import Observation, ObservationNode


def make_observation() -> Observation:
    return Observation(
        observation_id="obs-current",
        nodes=[
            ObservationNode(
                node_id="search",
                class_name="android.widget.EditText",
                content_description="Search",
                resource_id="search_box",
                editable=True,
                bounds=(0, 0, 100, 50),
            ),
            ObservationNode(
                node_id="buy-a",
                class_name="android.widget.Button",
                text="Buy now",
                clickable=True,
                bounds=(0, 50, 100, 100),
            ),
            ObservationNode(
                node_id="buy-b",
                class_name="android.widget.Button",
                text="Buy now",
                clickable=True,
                bounds=(0, 100, 100, 150),
            ),
        ],
    )


def test_resource_id_has_priority_over_text() -> None:
    result = TargetMatcher().match(
        ActionTarget(resource_id="search_box", text="Buy now"),
        make_observation(),
    )

    assert result.found is True
    assert result.node_id == "search"
    assert result.strategy is MatchStrategy.RESOURCE_ID


def test_exact_duplicate_text_is_rejected_as_ambiguous() -> None:
    result = TargetMatcher().match(ActionTarget(text="Buy now"), make_observation())

    assert result.found is False
    assert result.ambiguous is True
    assert set(result.candidates) == {"buy-a", "buy-b"}


def test_coordinate_fallback_uses_current_observation_bounds() -> None:
    result = TargetMatcher().match(
        ActionTarget(bounds=(0, 0, 100, 50)),
        make_observation(),
    )

    assert result.found is True
    assert result.strategy is MatchStrategy.COORDINATE_FALLBACK
    assert result.bounds == (0, 0, 100, 50)


def test_normalized_and_fuzzy_matching_are_available_after_exact_matching() -> None:
    observation = Observation(
        observation_id="obs-text",
        nodes=[ObservationNode(node_id="label", text="  商品 详情 ", bounds=(1, 1, 2, 2))],
    )

    normalized = TargetMatcher().match(ActionTarget(text="商品 详情"), observation)
    fuzzy = TargetMatcher(fuzzy_threshold=0.5).match(ActionTarget(semantic_hint="商品详"), observation)

    assert normalized.strategy is MatchStrategy.NORMALIZED_TEXT
    assert fuzzy.strategy is MatchStrategy.FUZZY_TEXT

