"""Deterministic fake action device for matcher/executor/verifier tests."""

from dataclasses import dataclass

from app.action.matcher import TargetMatch
from app.observation.models import Observation


@dataclass(frozen=True)
class FakeActionCall:
    name: str
    node_id: str | None = None
    value: str | None = None


class FakeActionDevice:
    """In-memory device with optional next-observation transitions."""

    def __init__(self, observation: Observation) -> None:
        self.current_observation = observation
        self.calls: list[FakeActionCall] = []
        self.next_observation: Observation | None = None
        self.reject_actions: set[str] = set()
        self.reject_once_actions: set[str] = set()

    def set_next_observation(self, observation: Observation) -> None:
        self.next_observation = observation

    def observe(self) -> Observation:
        return self.current_observation

    def click(self, target: TargetMatch) -> bool:
        return self._finish("click", target.node_id)

    def set_text(self, target: TargetMatch, value: str) -> bool:
        return self._finish("set_text", target.node_id, value)

    def scroll(self, target: TargetMatch | None, forward: bool) -> bool:
        return self._finish("scroll_forward" if forward else "scroll_backward", target.node_id if target else None)

    def back(self) -> bool:
        return self._finish("back")

    def wait(self, timeout_ms: int) -> bool:
        return self._finish("wait", value=str(timeout_ms))

    def stop(self) -> bool:
        return self._finish("stop")

    def _finish(self, name: str, node_id: str | None = None, value: str | None = None) -> bool:
        self.calls.append(FakeActionCall(name=name, node_id=node_id, value=value))
        if name in self.reject_actions:
            return False
        if name in self.reject_once_actions:
            self.reject_once_actions.remove(name)
            self.current_observation = self.current_observation.model_copy(
                update={"observation_id": f"{self.current_observation.observation_id}:{name}:rejected:{len(self.calls)}"}
            )
            return False
        if self.next_observation is not None:
            self.current_observation = self.next_observation
            self.next_observation = None
        else:
            self.current_observation = self.current_observation.model_copy(
                update={"observation_id": f"{self.current_observation.observation_id}:{name}:{len(self.calls)}"}
            )
        return True
