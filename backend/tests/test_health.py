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
    assert response.json() == {"status": "accepted", "observation_id": "obs-1"}
