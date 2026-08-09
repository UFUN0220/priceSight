"""Fresh-observation state transition verification."""

from pydantic import BaseModel

from app.observation.models import Observation, PageType


class VerificationExpectation(BaseModel):
    expected_page_type: PageType | None = None
    required_text: str | None = None
    forbidden_text: str | None = None
    require_observation_change: bool = True


class VerificationResult(BaseModel):
    verified: bool
    reason: str
    observation_id: str | None = None


class ActionVerifier:
    """Verify expected state using only the fresh post-action observation."""

    def verify(
        self,
        before: Observation,
        after: Observation | None,
        expectation: VerificationExpectation,
    ) -> VerificationResult:
        if after is None:
            return VerificationResult(verified=False, reason="post-action observation unavailable")
        if expectation.require_observation_change and after.observation_id == before.observation_id:
            return VerificationResult(
                verified=False,
                reason="observation did not change",
                observation_id=after.observation_id,
            )
        if expectation.expected_page_type and after.page_type is not expectation.expected_page_type:
            return VerificationResult(
                verified=False,
                reason="page type did not match expectation",
                observation_id=after.observation_id,
            )

        text = " ".join(
            value
            for node in after.nodes
            for value in (node.text, node.content_description)
            if value
        ).casefold()
        if expectation.required_text and expectation.required_text.casefold() not in text:
            return VerificationResult(
                verified=False,
                reason="required text was not observed",
                observation_id=after.observation_id,
            )
        if expectation.forbidden_text and expectation.forbidden_text.casefold() in text:
            return VerificationResult(
                verified=False,
                reason="forbidden text remained in observation",
                observation_id=after.observation_id,
            )
        return VerificationResult(verified=True, reason="expectation satisfied", observation_id=after.observation_id)
