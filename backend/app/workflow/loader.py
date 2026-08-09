"""Safe YAML loading for deterministic workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.action.models import ActionType
from app.workflow.models import WorkflowDefinition


class WorkflowLoadError(ValueError):
    """Raised when a YAML workflow is malformed or fails schema validation."""


class WorkflowLoader:
    """Load workflow definitions without executing or resolving any actions."""

    def from_path(self, path: str | Path) -> WorkflowDefinition:
        source = Path(path)
        try:
            text = source.read_text(encoding="utf-8")
        except OSError as error:
            raise WorkflowLoadError(f"unable to read workflow: {source}") from error
        return self.from_text(text, source=str(source))

    def from_text(self, text: str, *, source: str = "<string>") -> WorkflowDefinition:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise WorkflowLoadError(f"invalid YAML in {source}: {error}") from error
        if not isinstance(data, dict):
            raise WorkflowLoadError(f"workflow root in {source} must be a mapping")
        try:
            normalized = self._normalize_actions(data)
        except (KeyError, TypeError, ValueError) as error:
            raise WorkflowLoadError(f"invalid action in {source}: {error}") from error
        try:
            return WorkflowDefinition.model_validate(normalized)
        except ValidationError as error:
            raise WorkflowLoadError(f"invalid workflow schema in {source}: {error}") from error

    @staticmethod
    def _normalize_actions(data: dict[str, Any]) -> dict[str, Any]:
        """Accept readable lowercase YAML actions while keeping typed models strict."""

        normalized = dict(data)
        steps = normalized.get("steps")
        if not isinstance(steps, list):
            return normalized
        normalized["steps"] = [
            {
                **step,
                "action": ActionType(str(step["action"]).upper()).value,
            }
            if isinstance(step, dict) and "action" in step
            else step
            for step in steps
        ]
        return normalized
