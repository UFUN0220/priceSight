"""Tests for the phase 0 service shell."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_observation_debug_endpoint_accepts_serialized_observation() -> None:
    response = client.post(
        "/observations",
        json={
            "observation_id": "obs-1",
            "package_name": "com.example.shop",
            "timestamp_epoch_ms": 123,
            "nodes": [
                {
                    "node_id": "root:0",
                    "parent_id": None,
                    "class_name": "android.view.View",
                    "text": "商品",
                    "clickable": True,
                    "enabled": True,
                    "visible": True,
                    "bounds": [0, 0, 100, 100],
                    "depth": 0,
                    "children": [],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "observation_id": "obs-1",
        "device_id": "android-default",
    }


def test_device_bridge_api_completes_one_action_cycle() -> None:
    device_id = "api-cycle-device"
    observation_id = "api-cycle-obs"
    observation = {
        "observation_id": observation_id,
        "package_name": "com.example.shop",
        "timestamp_epoch_ms": 456,
        "nodes": [
            {
                "node_id": "root:0",
                "text": "商品详情",
                "clickable": True,
                "enabled": True,
                "visible": True,
                "bounds": [0, 0, 100, 100],
                "depth": 0,
                "children": [],
            }
        ],
    }
    assert client.post(
        "/observations", params={"device_id": device_id}, json=observation
    ).status_code == 200

    queued = client.post(
        f"/devices/{device_id}/actions",
        json={
            "action_type": "CLICK",
            "target": {"node_id": "root:0", "bounds": [0, 0, 100, 100]},
            "observation_id": observation_id,
        },
    )
    assert queued.status_code == 200
    command_id = queued.json()["command_id"]

    command = client.get(f"/devices/{device_id}/actions/next")
    assert command.status_code == 200
    assert command.json()["command_id"] == command_id

    result = client.post(
        f"/devices/{device_id}/action-results",
        json={
            "command_id": command_id,
            "result": {"success": True, "status": "SUCCESS"},
        },
    )
    assert result.status_code == 200
    assert client.get(f"/devices/{device_id}").json()["completed_action_count"] == 1


def test_device_bridge_api_rejects_stale_and_unsafe_actions() -> None:
    device_id = "api-guard-device"
    observation = {
        "observation_id": "guard-obs",
        "package_name": "com.example.shop",
        "timestamp_epoch_ms": 789,
        "nodes": [
            {
                "node_id": "root:0",
                "text": "确认支付",
                "clickable": True,
                "enabled": True,
                "visible": True,
                "bounds": [0, 0, 100, 100],
                "depth": 0,
                "children": [],
            }
        ],
    }
    assert client.post(
        "/observations", params={"device_id": device_id}, json=observation
    ).status_code == 200

    stale = client.post(
        f"/devices/{device_id}/actions",
        json={"action_type": "BACK", "observation_id": "older-obs"},
    )
    unsafe = client.post(
        f"/devices/{device_id}/actions",
        json={"action_type": "BACK", "observation_id": "guard-obs"},
    )

    assert stale.status_code == 409
    assert unsafe.status_code == 403
