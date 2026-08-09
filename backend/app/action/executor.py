"""Action grounding and execution harness over a device abstraction."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.action.matcher import TargetMatch, TargetMatcher
from app.action.models import ActionRequest, ActionResult, ActionStatus, ActionType
from app.action.verifier import ActionVerifier, VerificationExpectation
from app.core.safety import SafetyDecision, SafetyGuard
from app.observation.models import Observation


@runtime_checkable
class ActionDevice(Protocol):
    """Device-level action interface; Android transport implements this later."""

    def observe(self) -> Observation:
        """Return a fresh observation after an action."""

    def click(self, target: TargetMatch) -> bool:
        """Perform node action or fresh-bounds gesture click."""

    def set_text(self, target: TargetMatch, value: str) -> bool:
        """Set text on a matched editable node."""

    def scroll(self, target: TargetMatch | None, forward: bool) -> bool:
        """Perform a forward/backward scroll."""

    def back(self) -> bool:
        """Navigate back."""

    def wait(self, timeout_ms: int) -> bool:
        """Wait for a bounded interval."""

    def stop(self) -> bool:
        """Stop execution safely."""


class ActionExecutor:
    """Resolve, execute, re-observe, and optionally verify one action."""

    _target_actions = {
        ActionType.CLICK,
        ActionType.SET_TEXT,
        ActionType.SCROLL_FORWARD,
        ActionType.SCROLL_BACKWARD,
    }
    _required_target_actions = {ActionType.CLICK, ActionType.SET_TEXT}

    def __init__(
        self,
        matcher: TargetMatcher | None = None,
        verifier: ActionVerifier | None = None,
        safety_guard: SafetyGuard | None = None,
    ) -> None:
        self.matcher = matcher or TargetMatcher()
        self.verifier = verifier or ActionVerifier()
        self.safety_guard = safety_guard or SafetyGuard()

    def execute(
        self,
        action: ActionRequest,
        observation: Observation,
        device: ActionDevice,
        expectation: VerificationExpectation | None = None,
    ) -> ActionResult:
        if action.observation_id and action.observation_id != observation.observation_id:
            return ActionResult(
                success=False,
                status=ActionStatus.STALE_OBSERVATION,
                message="action was planned against a different observation",
                observation_id=observation.observation_id,
            )

        if action.action_type is ActionType.STOP:
            accepted = device.stop()
            return self._simple_result(accepted, action, "safe stop requested")

        safety_text = self._observation_text(observation)
        if action.value:
            safety_text += " " + action.value
        if action.target:
            safety_text += " " + " ".join(
                value
                for value in (
                    action.target.text,
                    action.target.content_description,
                    action.target.semantic_hint,
                )
                if value
            )
        if self.safety_guard.evaluate(safety_text).decision is SafetyDecision.STOP:
            return ActionResult(
                success=False,
                status=ActionStatus.SAFETY_BLOCKED,
                message="deterministic safety guard blocked the action",
                observation_id=observation.observation_id,
            )

        match = self.matcher.match(action.target, observation) if action.action_type in self._target_actions else None
        target_missing = match is None or not match.found
        target_supplied = action.target is not None
        if action.action_type in self._target_actions and (
            (action.action_type in self._required_target_actions and target_missing)
            or (target_supplied and target_missing)
        ):
            return ActionResult(
                success=False,
                status=ActionStatus.TARGET_NOT_FOUND,
                message=match.reason if match else "target required",
                observation_id=observation.observation_id,
                match_strategy=match.strategy.value if match and match.strategy else None,
            )

        try:
            accepted = self._perform(action, device, match)
        except TimeoutError as error:
            return ActionResult(
                success=False,
                status=ActionStatus.TIMEOUT,
                message=str(error) or "device action timed out",
                observation_id=observation.observation_id,
            )
        if not accepted:
            return ActionResult(
                success=False,
                status=ActionStatus.ACTION_REJECTED,
                message="device rejected the action",
                observation_id=observation.observation_id,
                matched_node_id=match.node_id if match else None,
                match_strategy=match.strategy.value if match and match.strategy else None,
            )

        fresh = device.observe()
        if expectation is not None:
            verification = self.verifier.verify(observation, fresh, expectation)
            if not verification.verified:
                return ActionResult(
                    success=False,
                    status=ActionStatus.STATE_UNCHANGED,
                    message=verification.reason,
                    observation_id=fresh.observation_id,
                    matched_node_id=match.node_id if match else None,
                    match_strategy=match.strategy.value if match and match.strategy else None,
                )
        return ActionResult(
            success=True,
            status=ActionStatus.SUCCESS,
            message="action executed and fresh observation obtained",
            observation_id=fresh.observation_id,
            matched_node_id=match.node_id if match else None,
            match_strategy=match.strategy.value if match and match.strategy else None,
            match_score=match.score if match else None,
        )

    def _perform(
        self,
        action: ActionRequest,
        device: ActionDevice,
        match: TargetMatch | None,
    ) -> bool:
        if action.action_type is ActionType.CLICK:
            return device.click(match)  # type: ignore[arg-type]
        if action.action_type is ActionType.SET_TEXT:
            if match is None or action.value is None:
                return False
            return device.set_text(match, action.value)
        if action.action_type is ActionType.SCROLL_FORWARD:
            return device.scroll(match, forward=True)
        if action.action_type is ActionType.SCROLL_BACKWARD:
            return device.scroll(match, forward=False)
        if action.action_type is ActionType.BACK:
            return device.back()
        if action.action_type is ActionType.WAIT:
            return device.wait(action.timeout_ms)
        return False

    @staticmethod
    def _observation_text(observation: Observation) -> str:
        return " ".join(
            value
            for node in observation.nodes
            for value in (node.text, node.content_description)
            if value
        )

    @staticmethod
    def _simple_result(accepted: bool, action: ActionRequest, message: str) -> ActionResult:
        return ActionResult(
            success=accepted,
            status=ActionStatus.SUCCESS if accepted else ActionStatus.ACTION_REJECTED,
            message=message,
        )
