"""Sanitization helpers for browser observations and read-only evidence."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from app.observation.models import Observation
from app.platform.web.models import WebEvidence


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)1\d{10}(?!\d)")
_LONG_NUMBER = re.compile(r"(?<!\d)\d{12,}(?!\d)")


def sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    sanitized = _EMAIL.sub("[REDACTED_EMAIL]", value)
    sanitized = _PHONE.sub("[REDACTED_PHONE]", sanitized)
    return _LONG_NUMBER.sub("[REDACTED_ID]", sanitized)


def sanitize_url(value: str | None) -> str | None:
    if not value:
        return value
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def sanitize_observation(observation: Observation) -> Observation:
    """Return a copy without query parameters or common personal identifiers."""

    return observation.model_copy(
        update={
            "source_url": sanitize_url(observation.source_url),
            "title": sanitize_text(observation.title),
            "nodes": [
                node.model_copy(
                    update={
                        "text": sanitize_text(node.text),
                        "content_description": sanitize_text(node.content_description),
                    }
                )
                for node in observation.nodes
            ],
        }
    )


def evidence_for(observation: Observation, platform_id: str) -> WebEvidence:
    sanitized = sanitize_observation(observation)
    return WebEvidence(
        platform_id=platform_id,
        page_type=sanitized.page_type.value,
        source_url=sanitized.source_url,
        title=sanitized.title,
        observation_id=sanitized.observation_id,
        captured_at=sanitized.captured_at.isoformat(),
        node_ids=[node.node_id for node in sanitized.nodes],
    )
