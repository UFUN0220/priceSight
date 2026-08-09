"""FastAPI application entrypoint for the phase 0 backend."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.observation.models import Observation
from app.transport.event import AccessibilityEvent, EventDrivenTransport


class HealthResponse(BaseModel):
    """Stable response contract for the service health probe."""

    status: str


class ObservationAccepted(BaseModel):
    """Acknowledgement returned by the phase 2 debug observation endpoint."""

    status: str
    observation_id: str


app = FastAPI(
    title="Mobile Price Agent Backend",
    version="0.1.0",
    description="Safe-mode backend shell with polling-compatible and event-driven observation transport.",
)
event_transport = EventDrivenTransport()


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return a process-level health response without touching external services."""

    return HealthResponse(status="ok")


@app.post("/observations", response_model=ObservationAccepted)
def receive_observation(observation: Observation) -> ObservationAccepted:
    """Accept one serialized observation for local Android debug export."""

    return ObservationAccepted(status="accepted", observation_id=observation.observation_id)


@app.websocket("/ws/transport")
async def receive_accessibility_events(websocket: WebSocket) -> None:
    """Receive serialized accessibility events over the event transport boundary."""

    await websocket.accept()
    try:
        while True:
            event = AccessibilityEvent.model_validate(await websocket.receive_json())
            event_transport.publish(event)
            await websocket.send_json(
                {"status": "accepted", "event_id": event.event_id, "observation_id": event.observation.observation_id}
            )
    except WebSocketDisconnect:
        return
