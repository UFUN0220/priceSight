"""Compact deterministic serialization for observation statistics and prompts."""

from app.observation.models import Observation


def serialize_observation(observation: Observation) -> str:
    """Serialize an observation without null fields for stable character counts."""

    return observation.model_dump_json(exclude_none=True)

