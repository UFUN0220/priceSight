"""Run the offline phase 11 reliability regression cases and save a report."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import cast

from app.action.fake import FakeActionDevice
from app.observation.models import Observation, ObservationNode, PageType
from app.workflow.engine import WorkflowEngine
from app.workflow.loader import WorkflowLoader
from app.workflow.models import WorkflowContext


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evaluation" / "reports" / "phase11_reliability.json"


def observation(*, duplicate: bool = False) -> Observation:
    nodes = [ObservationNode(node_id="search", text="Search", clickable=True)]
    if duplicate:
        nodes.append(ObservationNode(node_id="search-2", text="Search", clickable=True))
    return Observation(observation_id="phase11-obs", page_type=PageType.SEARCH, nodes=nodes)


def run_case(name: str, yaml_text: str, device: FakeActionDevice) -> dict[str, object]:
    workflow = WorkflowLoader().from_text(yaml_text)
    result = WorkflowEngine().run(
        workflow,
        WorkflowContext(task_id=f"phase11-{name}", goal=name),
        device,
    )
    return {
        "name": name,
        "status": result.status.value,
        "device_calls": len(device.calls),
        "trace_events": [event.model_dump(mode="json") for event in result.trace_events],
    }


def main() -> None:
    cases = [
        run_case(
            "target_missing",
            """
            name: target_missing
            steps:
              - id: click_coupon
                action: click
                target: {semantic_hint: coupon}
            """,
            FakeActionDevice(observation()),
        ),
        run_case(
            "duplicate_target",
            """
            name: duplicate_target
            steps:
              - id: click_search
                action: click
                target: {semantic_hint: search}
            """,
            FakeActionDevice(observation(duplicate=True)),
        ),
        run_case(
            "replan_after_repeated_failure",
            """
            name: replan_after_repeated_failure
            steps:
              - id: click_search
                action: click
                target: {semantic_hint: search}
                retry_limit: 2
            """,
            _rejecting_device(),
        ),
    ]
    observed = Counter(
        event["bad_case"]
        for case in cases
        for event in cast(list[dict[str, object]], case["trace_events"])
        if event["bad_case"] is not None
    )
    report = {
        "phase": 11,
        "scope": "offline action-harness reliability regression",
        "physical_device_connected": False,
        "real_platform_adapters_tested": False,
        "cases": cases,
        "bad_cases_observed": dict(observed),
        "replan_triggered": any(case["status"] == "NEEDS_AGENT_DECISION" for case in cases),
        "notes": [
            "Only deterministic offline harness cases are measured.",
            "UNEXPECTED_DIALOG, SPEC_AMBIGUITY, and page transition cases remain future fixtures until a real fixture is available.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _rejecting_device() -> FakeActionDevice:
    device = FakeActionDevice(observation())
    device.reject_actions.add("click")
    return device


if __name__ == "__main__":
    main()
