"""Disease detection endpoint tests: upload validation, model availability."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import Account

API = "/api/v1"


# ---------------------------------------------------------------------------
# Upload validation
# ---------------------------------------------------------------------------
async def test_a_non_image_content_type_is_rejected(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("notes.txt", b"this is not an image", "text/plain")},
    )
    assert response.status_code == 415
    assert "image" in response.json()["detail"].lower()


async def test_a_file_that_is_not_an_image_is_rejected(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("fake.png", b"this is definitely not a png", "image/png")},
    )
    assert response.status_code == 400
    assert "image" in response.json()["detail"].lower()


async def test_an_empty_file_is_rejected(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


async def test_an_unsupported_image_format_is_rejected(
    client: httpx.AsyncClient, account: Account, gif_image_bytes: bytes
):
    response = await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("animation.gif", gif_image_bytes, "image/gif")},
    )
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "gif" in detail or "supported" in detail


async def test_an_image_below_the_minimum_size_is_rejected(
    client: httpx.AsyncClient, account: Account, tiny_image_bytes: bytes
):
    response = await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("tiny.png", tiny_image_bytes, "image/png")},
    )
    assert response.status_code == 400
    assert "too small" in response.json()["detail"].lower()


async def test_an_oversized_upload_is_rejected(
    client: httpx.AsyncClient, account: Account, monkeypatch: pytest.MonkeyPatch
):
    """The upload is refused before the body is buffered in memory."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)

    payload = b"\x89PNG\r\n\x1a\n" + b"0" * 4096
    response = await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("big.png", payload, "image/png")},
    )
    assert response.status_code == 400
    assert "larger" in response.json()["detail"].lower() or "too large" in response.json()[
        "detail"
    ].lower()


async def test_the_upload_endpoint_requires_authentication(
    client: httpx.AsyncClient, leaf_image_bytes: bytes
):
    response = await client.post(
        f"{API}/disease/predict",
        files={"file": ("leaf.png", leaf_image_bytes, "image/png")},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Missing model
# ---------------------------------------------------------------------------
async def test_prediction_returns_503_when_the_model_is_not_trained(
    client: httpx.AsyncClient, account: Account, empty_model_dir, leaf_image_bytes: bytes
):
    """The API must report the missing model, never fabricate a prediction."""
    response = await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("leaf.png", leaf_image_bytes, "image/png")},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "train_cnn" in detail
    assert "not available" in detail.lower()


async def test_the_model_status_endpoint_reports_the_missing_model(
    client: httpx.AsyncClient, empty_model_dir
):
    response = await client.get(f"{API}/models/status")
    assert response.status_code == 200
    body = response.json()
    disease = next(m for m in body["models"] if m["key"] == "disease_detection")
    assert disease["available"] is False
    assert "train_cnn" in disease["message"]


# ---------------------------------------------------------------------------
# Successful inference (only when a trained model is installed)
# ---------------------------------------------------------------------------
def _disease_model_installed() -> bool:
    from ml.model_registry import registry

    return registry.is_disease_model_available()


@pytest.mark.skipif(
    not _disease_model_installed(),
    reason="The disease model has not been trained on this machine.",
)
async def test_prediction_returns_a_classification(
    client: httpx.AsyncClient, account: Account, leaf_image_bytes: bytes
):
    response = await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("leaf.png", leaf_image_bytes, "image/png")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["predicted_class"]
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["confidence_percent"] == pytest.approx(body["confidence"] * 100, rel=1e-3)
    assert isinstance(body["is_healthy"], bool)
    assert body["model_name"]
    assert body["model_version"]
    assert body["inference_ms"] >= 0
    assert len(body["top_predictions"]) == 5
    assert body["top_predictions"][0]["probability"] >= body["top_predictions"][-1][
        "probability"
    ]
    assert body["saved"] is True
    assert body["prediction_id"]


@pytest.mark.skipif(
    not _disease_model_installed(),
    reason="The disease model has not been trained on this machine.",
)
async def test_a_successful_prediction_is_stored_in_the_history(
    client: httpx.AsyncClient, account: Account, leaf_image_bytes: bytes
):
    await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("leaf.png", leaf_image_bytes, "image/png")},
    )

    response = await client.get(f"{API}/disease/history", headers=account.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1

    item = body["items"][0]
    detail = await client.get(
        f"{API}/disease/history/{item['id']}", headers=account.headers
    )
    assert detail.status_code == 200
    assert detail.json()["image_metadata"]["format"] == "PNG"


@pytest.mark.skipif(
    not _disease_model_installed(),
    reason="The disease model has not been trained on this machine.",
)
async def test_a_stored_prediction_can_be_deleted(
    client: httpx.AsyncClient, account: Account, leaf_image_bytes: bytes
):
    await client.post(
        f"{API}/disease/predict",
        headers=account.headers,
        files={"file": ("leaf.png", leaf_image_bytes, "image/png")},
    )

    history = await client.get(f"{API}/disease/history", headers=account.headers)
    prediction_id = history.json()["items"][0]["id"]

    deleted = await client.delete(
        f"{API}/disease/history/{prediction_id}", headers=account.headers
    )
    assert deleted.status_code == 200

    remaining = await client.get(f"{API}/disease/history", headers=account.headers)
    assert remaining.json()["pagination"]["total"] == 0
