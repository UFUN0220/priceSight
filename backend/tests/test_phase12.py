"""Phase 12 event transport, persistent cache, and metric regression tests."""

import asyncio
from pathlib import Path

from starlette.testclient import TestClient

from app.cache.offer import OfferCache
from app.comparison.engine import ComparisonEngine
from app.core.config import load_settings
from app.core.dependencies import build_container
from app.observation.models import Observation
from app.platform.fixture import FixtureOfferAdapter
from app.transport.event import EventDrivenTransport
from app.transport.fake import FakeDevice
from app.transport.polling import PollingTransport
from app.main import app


FIXTURES = Path("backend/tests/fixtures/platform/comparison")


def load_fixture(name: str) -> Observation:
    return Observation.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


def sources() -> list[tuple[FixtureOfferAdapter, Observation]]:
    return [
        (
            FixtureOfferAdapter("fixture-store-a", "com.pricesight.fixture.storea"),
            load_fixture("store_a.json"),
        ),
        (
            FixtureOfferAdapter("fixture-store-b", "com.pricesight.fixture.storeb"),
            load_fixture("store_b.json"),
        ),
    ]


def test_settings_support_polling_and_event_modes() -> None:
    settings = load_settings({"TRANSPORT_MODE": "event", "EVENT_STABILIZATION_MS": "10"})

    assert settings.transport_mode == "event"
    assert settings.event_stabilization_ms == 10


def test_event_mode_selects_event_transport_in_container() -> None:
    container = build_container(load_settings({"TRANSPORT_MODE": "event", "EVENT_STABILIZATION_MS": "0"}))

    assert isinstance(container.transport, EventDrivenTransport)


def test_websocket_transport_accepts_serialized_accessibility_event() -> None:
    payload = Observation(observation_id="ws-observation").model_dump(mode="json")

    with TestClient(app).websocket_connect("/ws/transport") as websocket:
        websocket.send_json({"event_id": "ws-event-1", "observation": payload})
        acknowledgement = websocket.receive_json()

    assert acknowledgement == {
        "status": "accepted",
        "event_id": "ws-event-1",
        "observation_id": "ws-observation",
    }


def test_polling_transport_waits_for_a_changed_observation() -> None:
    first = Observation(observation_id="first")
    second = Observation(observation_id="second")
    device = FakeDevice(first)
    transport = PollingTransport(device, poll_interval_ms=0)
    device.current_observation = second

    assert transport.wait_for_change(first, timeout_ms=20) == second


def test_event_transport_debounces_to_latest_observation() -> None:
    async def scenario() -> None:
        first = Observation(observation_id="first")
        second = Observation(observation_id="second")
        latest = Observation(observation_id="latest")
        transport = EventDrivenTransport(initial_observation=first, stabilization_ms=1)
        transport.publish_observation(second, event_id="event-1")
        transport.publish_observation(latest, event_id="event-2")

        observed = await transport.wait_for_change(first, timeout_ms=100)

        assert observed == latest
        assert transport.observe() == latest

    asyncio.run(scenario())


def test_offer_cache_persists_locally_and_reports_age(tmp_path) -> None:
    cache_path = tmp_path / "offers.sqlite3"
    engine = ComparisonEngine(cache=OfferCache(ttl_seconds=60, path=cache_path))
    first = engine.compare("可口可乐 500ml×2瓶", sources())
    engine.cache.close()

    reopened = OfferCache(ttl_seconds=60, path=cache_path)
    key = reopened.key(
        platform=first.offers[0].platform_id,
        store=first.offers[0].source_store,
        product=first.offers[0].identity.normalized_name,
        specification=first.offers[0].specification.model_dump_json(),
    )
    lookup = reopened.lookup(key)

    assert lookup.hit is True
    assert lookup.offer is not None
    assert lookup.age_seconds is not None
    assert lookup.age_seconds >= 0
    reopened.close()


def test_comparison_records_cache_hits_misses_and_metadata() -> None:
    engine = ComparisonEngine(cache=OfferCache(ttl_seconds=60))

    first = engine.compare("可口可乐 500ml×2瓶", sources())
    second = engine.compare("可口可乐 500ml×2瓶", sources())

    assert first.cache_hits == 0
    assert first.cache_misses == 2
    assert all(event.hit is False for event in first.cache_events)
    assert second.cache_hits == 2
    assert second.cache_misses == 0
    assert all(event.hit is True and event.age_seconds is not None for event in second.cache_events)
