"""Deterministic safety domain models and guard."""

import re

from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.exceptions import SafetyViolationError


class SafetyDecision(StrEnum):
    """Decision produced by deterministic safety inspection."""

    ALLOW = "ALLOW"
    STOP = "STOP"


class SafetyAssessment(BaseModel):
    """Auditable result of inspecting one piece of UI or action text."""

    decision: SafetyDecision
    reason_code: str | None = None
    matched_terms: list[str] = Field(default_factory=list)


class SafetyGuard:
    """Block high-risk purchase and security flows before execution exists."""

    _blocked_terms = (
        "submit order",
        "place order",
        "confirm order",
        "payment",
        "pay now",
        "password",
        "captcha",
        "identity verification",
        "提交订单",
        "确认订单",
        "确认下单",
        "下单",
        "付款",
        "支付",
        "支付密码",
        "验证码",
        "身份验证",
    )

    def evaluate(self, text: str | None) -> SafetyAssessment:
        """Return STOP when known payment, order, or security terms are present."""

        normalized = (text or "").casefold()
        compact = re.sub(r"[\W_]+", "", normalized)
        matched = [
            term
            for term in self._blocked_terms
            if term.casefold() in normalized
            or re.sub(r"[\W_]+", "", term.casefold()) in compact
        ]
        if matched:
            return SafetyAssessment(
                decision=SafetyDecision.STOP,
                reason_code="HIGH_RISK_FLOW",
                matched_terms=matched,
            )
        return SafetyAssessment(decision=SafetyDecision.ALLOW)

    def assert_allowed(self, text: str | None) -> None:
        """Raise a domain error when the inspected text is unsafe."""

        assessment = self.evaluate(text)
        if assessment.decision is SafetyDecision.STOP:
            raise SafetyViolationError(
                f"Safety stop: {assessment.reason_code}; terms={assessment.matched_terms}"
            )
