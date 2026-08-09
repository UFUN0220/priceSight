"""Tests for deterministic safety decisions."""

import pytest

from app.core.exceptions import SafetyViolationError
from app.core.safety import SafetyDecision, SafetyGuard


def test_safety_guard_allows_read_only_inspection() -> None:
    assessment = SafetyGuard().evaluate("查看商品价格和规格")

    assert assessment.decision is SafetyDecision.ALLOW
    assert assessment.matched_terms == []


def test_safety_guard_stops_payment_text() -> None:
    assessment = SafetyGuard().evaluate("确认支付并输入支付密码")

    assert assessment.decision is SafetyDecision.STOP
    assert "支付" in assessment.matched_terms
    assert "支付密码" in assessment.matched_terms


def test_safety_guard_raises_domain_error() -> None:
    with pytest.raises(SafetyViolationError):
        SafetyGuard().assert_allowed("submit order")


@pytest.mark.parametrize(
    "unsafe_text",
    ["支 付 密 码", "确 认 下 单", "PAY-NOW", "identity_verification"],
)
def test_safety_guard_stops_separator_obfuscation(unsafe_text: str) -> None:
    assert SafetyGuard().evaluate(unsafe_text).decision is SafetyDecision.STOP
