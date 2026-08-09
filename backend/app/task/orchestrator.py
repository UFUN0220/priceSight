"""Bounded task orchestration over the existing WorkflowEngine."""

from __future__ import annotations

from app.action.executor import ActionDevice
from app.workflow.engine import WorkflowEngine
from app.workflow.models import WorkflowContext, WorkflowDefinition, WorkflowResult


class TaskOrchestrator:
    """Keep runtime selection outside workflows and platform adapters."""

    def __init__(self, workflow_engine: WorkflowEngine | None = None) -> None:
        self.workflow_engine = workflow_engine or WorkflowEngine()

    def run(
        self,
        workflow: WorkflowDefinition,
        context: WorkflowContext,
        runtime: ActionDevice,
    ) -> WorkflowResult:
        """Run a finite workflow on any runtime implementing ActionDevice."""

        return self.workflow_engine.run(workflow, context, runtime)
