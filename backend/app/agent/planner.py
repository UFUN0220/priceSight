"""Provider-neutral, bounded planner for structured Agent decisions."""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.action.models import ActionType
from app.agent.models import AgentContext, AgentDecision, AgentPlanResult, AgentPlanStatus
from app.core.exceptions import ProviderError
from app.core.safety import SafetyDecision, SafetyGuard
from app.llm.base import LLMProvider, LLMRequest


class AgentPlanner:
    """Ask a provider for JSON and validate it before any action can execute."""

    def __init__(
        self,
        provider: LLMProvider,
        safety_guard: SafetyGuard | None = None,
        confidence_threshold: float = 0.6,
        max_calls: int = 3,
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if max_calls < 1:
            raise ValueError("max_calls must be positive")
        self.provider = provider
        self.safety_guard = safety_guard or SafetyGuard()
        self.confidence_threshold = confidence_threshold
        self.max_calls = max_calls

    def plan(self, context: AgentContext) -> AgentPlanResult:
        """Return a validated decision or an explicit non-executable outcome."""

        attempts_allowed = min(self.max_calls, context.retry_budget + 1)
        attempts = 0
        last_status = AgentPlanStatus.MALFORMED_OUTPUT
        last_reason = "provider returned no structured decision"
        last_provider: str | None = None

        while attempts < attempts_allowed:
            attempts += 1
            try:
                response = self.provider.complete(
                    LLMRequest(
                        system_prompt=self._system_prompt(),
                        prompt=self.build_prompt(context),
                    )
                )
                last_provider = response.provider
                decision = AgentDecision.model_validate_json(response.content)
            except (ValidationError, ValueError) as error:
                last_status = AgentPlanStatus.MALFORMED_OUTPUT
                last_reason = f"model output was not valid AgentDecision JSON: {error}"
                if attempts < attempts_allowed:
                    context.retry_budget -= 1
                    continue
                break
            except ProviderError as error:
                last_status = AgentPlanStatus.PROVIDER_ERROR
                last_reason = str(error)
                if attempts < attempts_allowed:
                    context.retry_budget -= 1
                    continue
                break

            invalid_reason = self._invalid_action_reason(decision)
            if invalid_reason is not None:
                last_status = AgentPlanStatus.INVALID_ACTION
                last_reason = invalid_reason
                if attempts < attempts_allowed:
                    context.retry_budget -= 1
                    continue
                break

            if decision.action is not None and self._is_unsafe(decision):
                return AgentPlanResult(
                    status=AgentPlanStatus.SAFETY_STOP,
                    decision=decision,
                    failure_reason="deterministic safety guard rejected the proposed action",
                    attempts=attempts,
                    provider=last_provider,
                )

            if decision.confidence < self.confidence_threshold:
                last_status = AgentPlanStatus.LOW_CONFIDENCE
                last_reason = (
                    f"decision confidence {decision.confidence:.2f} is below "
                    f"threshold {self.confidence_threshold:.2f}"
                )
                if attempts < attempts_allowed:
                    context.retry_budget -= 1
                    continue
                break

            if decision.action is None:
                return AgentPlanResult(
                    status=AgentPlanStatus.INVALID_ACTION,
                    decision=decision,
                    failure_reason="accepted decision must contain an action",
                    attempts=attempts,
                    provider=last_provider,
                )
            return AgentPlanResult(
                status=AgentPlanStatus.ACCEPTED,
                decision=decision,
                attempts=attempts,
                provider=last_provider,
            )

        final_status = AgentPlanStatus.RETRY_EXHAUSTED if attempts_allowed > 1 else last_status
        return AgentPlanResult(
            status=final_status,
            failure_reason=last_reason,
            attempts=attempts,
            provider=last_provider,
        )

    @staticmethod
    def build_prompt(context: AgentContext) -> str:
        """Serialize exactly the bounded fields permitted in planner context."""

        observation = context.observation
        payload = {
            "user_goal": context.user_goal,
            "current_page_type": observation.page_type.value if observation else "unknown",
            "compact_observation": observation.model_dump(mode="json") if observation else None,
            "workflow_state": context.workflow_state,
            "previous_important_action": context.previous_action.model_dump(mode="json")
            if context.previous_action
            else None,
            "known_constraints": context.known_constraints,
            "retry_budget": context.retry_budget,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _system_prompt() -> str:
        return (
            "Return only one JSON object matching AgentDecision. "
            "Do not include Markdown, prose, coordinates copied from stale history, or unknown fields."
        )

    @staticmethod
    def _invalid_action_reason(decision: AgentDecision) -> str | None:
        action = decision.action
        if action is None:
            return None
        if action.action_type in {ActionType.CLICK, ActionType.SET_TEXT} and action.target is None:
            return "click and set_text decisions require a target"
        if action.action_type is ActionType.SET_TEXT and action.value is None:
            return "set_text decisions require a value"
        return None

    def _is_unsafe(self, decision: AgentDecision) -> bool:
        action = decision.action
        if action is None:
            return False
        text = action.model_dump_json()
        return self.safety_guard.evaluate(text).decision is SafetyDecision.STOP
