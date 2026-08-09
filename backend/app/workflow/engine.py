"""Bounded sequential workflow execution over the phase 4 action harness."""

from __future__ import annotations

from time import perf_counter

from app.action.executor import ActionDevice, ActionExecutor
from app.action.models import ActionRequest, ActionResult, ActionStatus, ActionType
from app.action.verifier import VerificationExpectation
from app.core.reliability import (
    ActionTraceEvent,
    RepetitionDetector,
    classify_bad_case,
    observation_hash,
    target_summary,
)
from app.core.safety import SafetyDecision, SafetyGuard
from app.workflow.models import (
    PlannedStep,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowResult,
    WorkflowStatus,
    WorkflowStep,
)


class WorkflowEngine:
    """Execute finite workflows without invoking an LLM."""

    def __init__(
        self,
        action_executor: ActionExecutor | None = None,
        safety_guard: SafetyGuard | None = None,
        max_steps: int = 20,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self.action_executor = action_executor or ActionExecutor()
        self.safety_guard = safety_guard or SafetyGuard()
        self.max_steps = max_steps

    def run(
        self,
        workflow: WorkflowDefinition,
        context: WorkflowContext,
        device: ActionDevice,
    ) -> WorkflowResult:
        context.status = WorkflowStatus.RUNNING
        current = context.current_observation or device.observe()
        context.current_observation = current
        by_id = {step.id: step for step in workflow.steps}
        index = 0
        action_results: list[ActionResult] = []
        repetition_detector = RepetitionDetector()

        while index < len(workflow.steps):
            if context.step_count >= self.max_steps:
                return self._failure(context, action_results, None, "workflow step limit exhausted", current)
            step = workflow.steps[index]
            context.current_step_id = step.id
            context.step_count += 1

            safety = self.safety_guard.evaluate(self._observation_text(current))
            if safety.decision is SafetyDecision.STOP:
                device.stop()
                return self._safety_stop(
                    context,
                    action_results,
                    step.id,
                    safety.reason_code or "deterministic safety guard stopped the workflow",
                    current,
                )

            guard_failure = self._guard_failure(step, current)
            if guard_failure is not None:
                if step.optional:
                    context.skipped_steps.append(step.id)
                    if step.on_failure == "NEEDS_AGENT_DECISION":
                        return self._needs_agent(context, action_results, step.id, guard_failure, current)
                    index = self._next_index(step, by_id, success=False, fallback=index + 1)
                    continue
                return self._failure(context, action_results, step.id, guard_failure, current)

            if step.requires_agent_decision:
                return self._needs_agent(context, action_results, step.id, "workflow step explicitly requires an agent decision", current)
            if step.requires_cart_opt_in and not context.allow_cart:
                device.stop()
                return self._safety_stop(
                    context,
                    action_results,
                    step.id,
                    "cart action requires explicit allow_cart=True",
                    current,
                )

            try:
                planned = self._plan(step, context, current)
            except ValueError as error:
                return self._failure(context, action_results, step.id, str(error), current)

            result = self._execute_with_retries(
                planned,
                step,
                current,
                device,
                context,
                repetition_detector,
            )
            action_results.append(result)
            context.previous_result = result
            if result.status is ActionStatus.REPLAN_REQUIRED:
                return self._needs_agent(
                    context,
                    action_results,
                    step.id,
                    result.message or "repeated observation/action requires replanning",
                    current,
                )
            if result.status is ActionStatus.SAFETY_BLOCKED:
                device.stop()
                return self._safety_stop(context, action_results, step.id, result.message or "action safety blocked", current)
            if result.success:
                context.completed_steps.append(step.id)
                current = device.observe()
                context.current_observation = current
                if step.on_success == "NEEDS_AGENT_DECISION":
                    return self._needs_agent(context, action_results, step.id, "success route requires an agent decision", current)
                index = self._next_index(step, by_id, success=True, fallback=index + 1)
                continue
            if step.optional:
                context.skipped_steps.append(step.id)
                if step.on_failure == "NEEDS_AGENT_DECISION":
                    return self._needs_agent(context, action_results, step.id, result.message or result.status.value, current)
                index = self._next_index(step, by_id, success=False, fallback=index + 1)
                continue
            failure_reason = result.message or result.status.value
            failure_route = step.on_failure
            if failure_route == "NEEDS_AGENT_DECISION":
                return self._needs_agent(context, action_results, step.id, failure_reason, current)
            if failure_route is not None:
                index = self._route_index(failure_route, by_id)
                continue
            return self._failure(context, action_results, step.id, failure_reason, current)

        context.status = WorkflowStatus.SUCCEEDED
        return WorkflowResult(
            status=context.status,
            completed_steps=list(context.completed_steps),
            skipped_steps=list(context.skipped_steps),
            final_observation=current,
            action_results=action_results,
            trace_events=list(context.trace_events),
            context=context,
        )

    def _execute_with_retries(
        self,
        planned: PlannedStep,
        step: WorkflowStep,
        observation,
        device: ActionDevice,
        context: WorkflowContext,
        repetition_detector: RepetitionDetector,
    ) -> ActionResult:
        last_result: ActionResult | None = None
        for attempt in range(step.retry_limit + 1):
            if attempt:
                context.retry_count += 1
                observation = device.observe()
                context.current_observation = observation
                planned = planned.model_copy(
                    update={
                        "request": planned.request.model_copy(update={"observation_id": observation.observation_id})
                    }
                )
            started = perf_counter()
            if repetition_detector.register(observation, planned.request):
                last_result = ActionResult(
                    success=False,
                    status=ActionStatus.REPLAN_REQUIRED,
                    message="same action was requested against the same observation repeatedly",
                    observation_id=observation.observation_id,
                )
                self._record_trace(context, step.id, planned.request, last_result, observation, started, attempt)
                return last_result
            last_result = self.action_executor.execute(
                planned.request,
                observation,
                device,
                planned.expectation,
            )
            self._record_trace(context, step.id, planned.request, last_result, observation, started, attempt)
            if last_result.success or last_result.status is ActionStatus.SAFETY_BLOCKED:
                return last_result
        assert last_result is not None
        return last_result.model_copy(
            update={
                "status": ActionStatus.RETRY_EXHAUSTED,
                "message": f"step failed after {step.retry_limit + 1} attempt(s): {last_result.message or last_result.status.value}",
            }
        )

    @staticmethod
    def _record_trace(context, step_id, request, result, observation, started, retry_count) -> None:
        context.trace_events.append(
            ActionTraceEvent(
                task_id=context.task_id,
                step_id=step_id,
                observation_hash=observation_hash(observation),
                action_type=request.action_type.value,
                target_summary=target_summary(request),
                match_strategy=result.match_strategy,
                confidence=result.match_score,
                execution_result=result.status,
                latency_ms=(perf_counter() - started) * 1000,
                retry_count=retry_count,
                bad_case=classify_bad_case(result),
            )
        )

    @staticmethod
    def _plan(step: WorkflowStep, context: WorkflowContext, observation) -> PlannedStep:
        value = step.value
        if step.value_from is not None:
            if not step.value_from.startswith("task."):
                raise ValueError("value_from must use the task.<field> form")
            key = step.value_from.removeprefix("task.")
            value = context.task.get(key)
            if value is None:
                raise ValueError(f"task value is missing: {step.value_from}")
        if step.action in {ActionType.CLICK, ActionType.SET_TEXT} and step.target is None:
            raise ValueError("deterministic action requires a target; use requires_agent_decision for ambiguity")
        return PlannedStep(
            request=ActionRequest(
                action_type=step.action,
                target=step.target,
                value=value,
                observation_id=observation.observation_id,
                timeout_ms=step.timeout_ms,
            ),
            expectation=step.expected,
        )

    @staticmethod
    def _guard_failure(step: WorkflowStep, observation) -> str | None:
        if step.guard is None:
            return None
        guard = step.guard
        if guard.expected_page_type and observation.page_type is not guard.expected_page_type:
            return f"guard expected page type {guard.expected_page_type.value}"
        text = WorkflowEngine._observation_text(observation).casefold()
        if guard.required_text and guard.required_text.casefold() not in text:
            return "guard required text was not observed"
        if guard.forbidden_text and guard.forbidden_text.casefold() in text:
            return "guard forbidden text was observed"
        return None

    @staticmethod
    def _next_index(step: WorkflowStep, by_id: dict[str, WorkflowStep], *, success: bool, fallback: int) -> int:
        route = step.on_success if success else step.on_failure
        return fallback if route is None else WorkflowEngine._route_index(route, by_id)

    @staticmethod
    def _route_index(route: str, by_id: dict[str, WorkflowStep]) -> int:
        # The caller validates IDs at load time; this lookup is kept explicit for runtime safety.
        ids = list(by_id)
        if route not in by_id:
            raise ValueError(f"unknown workflow route: {route}")
        return ids.index(route)

    @staticmethod
    def _observation_text(observation) -> str:
        return " ".join(
            value
            for node in observation.nodes
            for value in (node.text, node.content_description)
            if value
        )

    @staticmethod
    def _failure(context, results, step_id, reason, observation) -> WorkflowResult:
        context.status = WorkflowStatus.FAILED
        return WorkflowResult(
            status=context.status,
            completed_steps=list(context.completed_steps),
            skipped_steps=list(context.skipped_steps),
            failed_step_id=step_id,
            failure_reason=reason,
            final_observation=observation,
            action_results=results,
            trace_events=list(context.trace_events),
            context=context,
        )

    @staticmethod
    def _needs_agent(context, results, step_id, reason, observation) -> WorkflowResult:
        context.status = WorkflowStatus.NEEDS_AGENT_DECISION
        return WorkflowResult(
            status=context.status,
            completed_steps=list(context.completed_steps),
            skipped_steps=list(context.skipped_steps),
            failed_step_id=step_id,
            failure_reason=reason,
            final_observation=observation,
            action_results=results,
            trace_events=list(context.trace_events),
            agent_decision_step_id=step_id,
            context=context,
        )

    @staticmethod
    def _safety_stop(context, results, step_id, reason, observation) -> WorkflowResult:
        context.status = WorkflowStatus.SAFETY_STOP
        return WorkflowResult(
            status=context.status,
            completed_steps=list(context.completed_steps),
            skipped_steps=list(context.skipped_steps),
            failed_step_id=step_id,
            failure_reason=reason,
            final_observation=observation,
            action_results=results,
            trace_events=list(context.trace_events),
            context=context,
        )
