"""Tests for YAML workflow schema validation and loading."""

import pytest

from app.action.models import ActionType
from app.workflow.loader import WorkflowLoadError, WorkflowLoader


def test_loader_accepts_lowercase_yaml_actions() -> None:
    workflow = WorkflowLoader().from_text(
        """
        name: search_product
        steps:
          - id: input_keyword
            action: set_text
            target:
              semantic_hint: search_input
            value_from: task.product_keyword
        """
    )

    assert workflow.steps[0].action is ActionType.SET_TEXT
    assert workflow.steps[0].value_from == "task.product_keyword"


def test_loader_rejects_duplicate_step_ids() -> None:
    with pytest.raises(WorkflowLoadError, match="unique"):
        WorkflowLoader().from_text(
            """
            name: invalid
            steps:
              - id: same
                action: wait
              - id: same
                action: wait
            """
        )


def test_loader_wraps_invalid_action() -> None:
    with pytest.raises(WorkflowLoadError, match="invalid action"):
        WorkflowLoader().from_text(
            """
            name: invalid_action
            steps:
              - id: unknown
                action: teleport
            """
        )


def test_loader_reads_repository_workflows() -> None:
    loader = WorkflowLoader()
    workflow = loader.from_path("workflows/add_to_cart.yaml")

    assert workflow.name == "add_to_cart"
    assert workflow.steps[0].requires_cart_opt_in is True
