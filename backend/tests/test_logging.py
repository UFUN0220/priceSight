"""Tests for the phase 1 structured logging formatter."""

import json
import logging

from app.core.logging import StructuredFormatter


def test_structured_formatter_emits_safe_stable_fields() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="step completed",
        args=(),
        exc_info=None,
    )
    record.context = {"task_id": "task-1", "step_id": "step-1"}

    payload = json.loads(StructuredFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "step completed"
    assert payload["context"]["task_id"] == "task-1"

