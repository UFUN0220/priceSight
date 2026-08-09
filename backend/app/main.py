"""FastAPI entrypoint for local observation and action transport."""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Query, Response, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from app.action.models import ActionRequest
from app.core.config import load_settings
from app.core.dependencies import build_container
from app.core.exceptions import ObservationUnavailableError, SafetyViolationError
from app.observation.models import Observation
from app.transport.event import AccessibilityEvent, EventDrivenTransport
from app.transport.session import (
    DeviceActionCommand,
    DeviceActionResultReport,
    DeviceSessionSnapshot,
)
from app.transport.store import SessionQueueFullError


class HealthResponse(BaseModel):
    status: str


class ObservationAccepted(BaseModel):
    status: str
    observation_id: str
    device_id: str


class ActionQueued(BaseModel):
    status: str
    command_id: str


class ActionResultAccepted(BaseModel):
    status: str
    command_id: str


settings = load_settings()
event_transport = EventDrivenTransport(stabilization_ms=settings.event_stabilization_ms)
container = build_container(
    settings=settings,
    transport=event_transport if settings.transport_mode == "event" else None,
)
device_sessions = container.device_sessions

app = FastAPI(
    title="Mobile Price Agent Backend",
    version="0.2.0",
    description="Safe-mode local backend with observation, action, polling, and event transport.",
)
app.state.container = container
app.state.event_transport = event_transport
app.state.device_sessions = device_sessions


def _verify_device_token(token: str | None) -> None:
    expected = settings.device_shared_token
    if expected and token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid device token")


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/observations", response_model=ObservationAccepted)
def receive_observation(
    observation: Observation,
    device_id: str = Query(default="android-default", min_length=1, max_length=128),
    x_device_token: str | None = Header(default=None),
) -> ObservationAccepted:
    """Store the latest device observation and publish it to the event path."""

    _verify_device_token(x_device_token)
    device_sessions.receive_observation(device_id, observation)
    event_transport.publish_observation(
        observation,
        event_id=f"http-{device_id}-{observation.observation_id}",
    )
    return ObservationAccepted(
        status="accepted",
        observation_id=observation.observation_id,
        device_id=device_id,
    )


@app.post("/devices/{device_id}/actions", response_model=ActionQueued)
def queue_action(
    device_id: str,
    action: ActionRequest,
    x_device_token: str | None = Header(default=None),
) -> ActionQueued:
    """Queue one already planned action after freshness and safety checks."""

    _verify_device_token(x_device_token)
    try:
        command = device_sessions.enqueue_action(device_id, action)
    except ObservationUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except SessionQueueFullError as error:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error)) from error
    except SafetyViolationError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    return ActionQueued(status="queued", command_id=command.command_id)


@app.get("/devices/{device_id}/actions/next", response_model=DeviceActionCommand)
def next_action(
    device_id: str,
    x_device_token: str | None = Header(default=None),
) -> DeviceActionCommand | Response:
    """Lease the next queued action, or return HTTP 204 when none is available."""

    _verify_device_token(x_device_token)
    command = device_sessions.next_action(device_id)
    return command if command is not None else Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/devices/{device_id}/action-results", response_model=ActionResultAccepted)
def receive_action_result(
    device_id: str,
    report: DeviceActionResultReport,
    x_device_token: str | None = Header(default=None),
) -> ActionResultAccepted:
    _verify_device_token(x_device_token)
    try:
        device_sessions.record_result(device_id, report)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return ActionResultAccepted(status="accepted", command_id=report.command_id)


@app.get("/devices/{device_id}", response_model=DeviceSessionSnapshot)
def device_snapshot(
    device_id: str,
    x_device_token: str | None = Header(default=None),
) -> DeviceSessionSnapshot:
    _verify_device_token(x_device_token)
    return device_sessions.snapshot(device_id)


@app.websocket("/ws/transport")
async def receive_accessibility_events(websocket: WebSocket) -> None:
    """Receive serialized accessibility events on the same process event transport."""

    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            if len(str(payload)) > settings.max_transport_message_chars:
                await websocket.close(code=1009, reason="message too large")
                return
            event = AccessibilityEvent.model_validate(payload)
            event_transport.publish(event)
            device_sessions.receive_observation("websocket-default", event.observation)
            await websocket.send_json(
                {
                    "status": "accepted",
                    "event_id": event.event_id,
                    "observation_id": event.observation.observation_id,
                }
            )
    except WebSocketDisconnect:
        return
