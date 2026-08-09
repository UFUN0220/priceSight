"""Quality-gate regression for the Runtime-independent task orchestrator."""

from app.task import TaskOrchestrator


class RecordingWorkflowEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object, object]] = []

    def run(self, workflow, context, runtime):
        self.calls.append((workflow, context, runtime))
        return "workflow-result"


def test_task_orchestrator_delegates_without_selecting_a_runtime() -> None:
    engine = RecordingWorkflowEngine()
    orchestrator = TaskOrchestrator(engine)
    workflow = object()
    context = object()
    runtime = object()

    assert orchestrator.run(workflow, context, runtime) == "workflow-result"
    assert engine.calls == [(workflow, context, runtime)]
