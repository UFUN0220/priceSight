"""Tests for sanitized web evidence output."""

from app.observation.models import Observation, ObservationNode
from app.platform.web.evidence import evidence_for, sanitize_observation


def test_web_evidence_redacts_identifiers_and_url_query() -> None:
    observation = Observation(
        observation_id="obs-1",
        platform="example-web",
        package_name="shop.example",
        source_url="https://shop.example/search?phone=13800138000&token=secret",
        title="用户 test@example.com",
        nodes=[
            ObservationNode(
                node_id="n1",
                text="联系电话 13800138000，订单 123456789012",
            )
        ],
    )

    sanitized = sanitize_observation(observation)
    evidence = evidence_for(observation, "example-web")

    assert sanitized.source_url == "https://shop.example/search"
    assert "test@example.com" not in (sanitized.title or "")
    assert "13800138000" not in (sanitized.nodes[0].text or "")
    assert "123456789012" not in (sanitized.nodes[0].text or "")
    assert evidence.source_url == "https://shop.example/search"
