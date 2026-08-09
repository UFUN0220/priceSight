"""Repeatable phase 8 E2E tests over the mock shopping state machine."""

from decimal import Decimal

from app.action.matcher import TargetMatch
from app.platform.mock_e2e import run_mock_e2e
from app.platform.mock_shopping import MockPage, MockShoppingDevice
from app.workflow.models import WorkflowStatus


def test_mock_device_exposes_required_pages_and_accessibility_edge_cases() -> None:
    device = MockShoppingDevice()

    home = device.observe()
    assert any(node.clickable and not node.text and node.content_description == "empty_action" for node in home.nodes)
    device.click(TargetMatch(found=True, node_id="home.search"))
    search = device.observe()
    assert any(node.editable and node.content_description == "search_input" for node in search.nodes)
    assert device.state.page is MockPage.SEARCH
    assert device.compression_stats[-1].raw_node_count >= device.compression_stats[-1].compressed_node_count


def test_mock_e2e_completes_comparison_and_stops_before_order_submission() -> None:
    result = run_mock_e2e()

    assert result.task_success is True
    assert result.safety_result is WorkflowStatus.SAFETY_STOP
    assert result.final_price == Decimal("10.90")
    assert result.llm_calls == 1
    assert result.compression_runs > 0
    assert result.steps > 0
    assert result.action_attempts > 0
    assert result.action_success_rate == 1.0
    assert result.safety_stop_correct is True


def test_mock_e2e_agent_handoff_is_part_of_the_runtime_contract() -> None:
    # The public E2E result records one provider call; this assertion protects the Agent route contract.
    result = run_mock_e2e()
    assert result.llm_calls == 1
