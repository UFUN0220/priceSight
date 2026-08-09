"""Measure polling/event delivery and warm-cache/task metrics offline."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time

from app.cache.offer import OfferCache
from app.comparison.engine import ComparisonEngine
from app.observation.models import Observation
from app.platform.fixture import FixtureOfferAdapter
from app.platform.mock_e2e import run_mock_e2e
from app.transport.event import EventDrivenTransport
from app.transport.fake import FakeDevice
from app.transport.polling import PollingTransport


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "backend" / "tests" / "fixtures" / "platform" / "comparison"
REPORT = ROOT / "evaluation" / "reports" / "phase12_benchmark.json"
ITERATIONS = 10


def load(name: str) -> Observation:
    return Observation.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


def comparison_sources() -> list[tuple[FixtureOfferAdapter, Observation]]:
    return [
        (FixtureOfferAdapter("fixture-store-a", "com.pricesight.fixture.storea"), load("store_a.json")),
        (FixtureOfferAdapter("fixture-store-b", "com.pricesight.fixture.storeb"), load("store_b.json")),
    ]


def summarize(values: list[float]) -> dict[str, float | int]:
    return {
        "sample_count": len(values),
        "mean_ms": statistics.fmean(values),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def polling_samples() -> list[float]:
    device = FakeDevice(Observation(observation_id="polling-initial"))
    transport = PollingTransport(device, poll_interval_ms=1)
    samples: list[float] = []
    for index in range(ITERATIONS):
        previous = Observation(observation_id=f"polling-before-{index}")
        next_observation = Observation(observation_id=f"polling-after-{index}")
        device.current_observation = previous
        publisher = threading.Thread(
            target=_publish_after_delay,
            args=(device, next_observation),
            daemon=True,
        )
        started = time.perf_counter()
        publisher.start()
        observed = transport.wait_for_change(previous, timeout_ms=100)
        publisher.join()
        samples.append((time.perf_counter() - started) * 1000)
        if observed is None:
            raise RuntimeError("polling benchmark failed to observe a changed state")
    return samples


async def event_samples() -> list[float]:
    transport = EventDrivenTransport(stabilization_ms=1)
    samples: list[float] = []
    for index in range(ITERATIONS):
        previous = Observation(observation_id=f"event-before-{index}")
        next_observation = Observation(observation_id=f"event-after-{index}")
        started = time.perf_counter()
        publisher = asyncio.create_task(_publish_event_after_delay(transport, next_observation, f"event-{index}"))
        observed = await transport.wait_for_change(previous, timeout_ms=100)
        await publisher
        samples.append((time.perf_counter() - started) * 1000)
        if observed is None:
            raise RuntimeError("event benchmark failed to observe a changed state")
    return samples


def _publish_after_delay(device: FakeDevice, observation: Observation) -> None:
    time.sleep(0.001)
    device.current_observation = observation


async def _publish_event_after_delay(
    transport: EventDrivenTransport,
    observation: Observation,
    event_id: str,
) -> None:
    await asyncio.sleep(0.001)
    transport.publish_observation(observation, event_id=event_id)


def cache_metrics() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="pricesight-phase12-") as directory:
        cache = OfferCache(ttl_seconds=300, path=Path(directory) / "offers.sqlite3")
        try:
            engine = ComparisonEngine(cache=cache)
            first = engine.compare("可口可乐 500ml×2瓶", comparison_sources())
            second = engine.compare("可口可乐 500ml×2瓶", comparison_sources())
            return {
                "first_run": {
                    "hits": first.cache_hits,
                    "misses": first.cache_misses,
                    "events": [event.model_dump(mode="json") for event in first.cache_events],
                },
                "second_run": {
                    "hits": second.cache_hits,
                    "misses": second.cache_misses,
                    "hit_rate": second.cache_hits / len(second.cache_events) if second.cache_events else 0.0,
                    "events": [event.model_dump(mode="json") for event in second.cache_events],
                },
            }
        finally:
            cache.close()


def task_metrics() -> dict[str, object]:
    results = [run_mock_e2e() for _ in range(ITERATIONS)]
    return {
        "sample_count": len(results),
        "task_success_rate": sum(result.task_success for result in results) / len(results),
        "average_llm_calls_per_task": statistics.fmean(result.llm_calls for result in results),
        "average_steps_per_task": statistics.fmean(result.steps for result in results),
        "raw_results": [result.model_dump(mode="json") for result in results],
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    polling = polling_samples()
    event = asyncio.run(event_samples())
    report = {
        "phase": 12,
        "scope": "offline transport and cache efficiency benchmark",
        "physical_device_connected": False,
        "real_platforms_contacted": [],
        "conditions": {
            "iterations": ITERATIONS,
            "poll_interval_ms": 1,
            "event_stabilization_ms": 1,
            "simulated_delivery_delay_ms": 1,
            "sources": ["fixture-store-a", "fixture-store-b"],
            "task": "mock shopping safe-mode E2E",
        },
        "polling_latency_ms": {**summarize(polling), "raw_samples": polling},
        "event_driven_latency_ms": {**summarize(event), "raw_samples": event},
        "cache": cache_metrics(),
        "tasks": task_metrics(),
        "notes": [
            "All measurements are local synthetic/fake-device runs in this environment.",
            "Latency values are observations from this run, not production performance claims.",
            "Real Meituan/JD/Taobao apps and physical Android devices were not used.",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
