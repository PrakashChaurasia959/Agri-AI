"""Shared fixtures for the AgriVision AI backend test-suite.

The suite runs entirely offline:

* MongoDB is replaced by the ``mongomock`` based in-memory emulator in
  :mod:`app.database.memory`, so the *real* repositories and the *real*
  endpoint handlers are exercised without needing a live Atlas cluster.
* The weather provider is replaced by an ``httpx`` mock transport.
* The machine-learning models are replaced by an empty model directory when a
  test needs the "model has not been trained" behaviour, and the real trained
  artifacts are used when they are present.
"""

from __future__ import annotations

import io
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Environment overrides.
#
# These MUST be applied before the application modules are imported, because
# `get_settings()` is an `lru_cache`-d accessor that is evaluated at import
# time.  Environment variables take precedence over the ``.env`` file in
# pydantic-settings, so these win over `backend/.env`.
# ---------------------------------------------------------------------------
os.environ["ENVIRONMENT"] = "test"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["JWT_SECRET_KEY"] = (
    "test-only-secret-key-never-use-this-outside-the-test-suite-0123456789"
)
os.environ["MONGODB_URI"] = ""
os.environ["COOKIE_SECURE"] = "false"
os.environ["DEBUG"] = "false"
# Argon2 is deliberately expensive in production (t=3, m=64 MiB).  The tests
# hash a password on almost every request, so the cost is lowered here to keep
# the suite fast.  The *algorithm* under test is unchanged - only the work
# factor differs.
os.environ["ARGON2_TIME_COST"] = "1"
os.environ["ARGON2_MEMORY_COST"] = "8192"
os.environ["ARGON2_PARALLELISM"] = "1"

import httpx  # noqa: E402  (imported after the environment overrides)

DEFAULT_PASSWORD = "AgriVision#2024"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: marks tests that take a long time")


# ---------------------------------------------------------------------------
# Account helper
# ---------------------------------------------------------------------------
@dataclass
class Account:
    """A registered user plus the credentials needed to act as them."""

    id: str
    name: str
    email: str
    password: str
    access_token: str
    csrf_token: str | None = None
    role: str = "user"
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    @classmethod
    def from_payload(cls, payload: dict[str, Any], password: str) -> "Account":
        user = payload["user"]
        return cls(
            id=str(user["id"]),
            name=user["name"],
            email=user["email"],
            password=password,
            access_token=payload["access_token"],
            csrf_token=payload.get("csrf_token"),
            role=user.get("role", "user"),
        )


async def register_user(
    client: httpx.AsyncClient,
    *,
    email: str = "farmer@example.com",
    password: str = DEFAULT_PASSWORD,
    name: str = "Test Farmer",
    **extra: Any,
) -> dict[str, Any]:
    """Register a user and return the raw token payload."""
    body: dict[str, Any] = {"name": name, "email": email, "password": password}
    body.update(extra)
    response = await client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201, f"register failed: {response.text}"
    return response.json()


def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """Read the double-submit CSRF token out of the client cookie jar."""
    token = client.cookies.get("agrivision_csrf")
    return {"X-CSRF-Token": token} if token else {}


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------
def _install_memory_manager(monkeypatch: pytest.MonkeyPatch, manager: Any) -> None:
    """Point every ``db_manager`` reference at the in-memory emulator.

    The application modules do ``from app.database.connection import
    db_manager``, which binds the object at import time.  Replacing the
    attribute on every module that holds a reference keeps the production code
    completely unmodified while still letting the tests run offline.
    """
    for module in list(sys.modules.values()):
        if module is None:
            continue
        if "db_manager" in vars(module):
            monkeypatch.setattr(module, "db_manager", manager)


@pytest.fixture()
async def memory_db(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Any]:
    """An in-memory MongoDB emulator wired into the application."""
    from app.database.memory import MemoryDatabaseManager

    manager = MemoryDatabaseManager()
    await manager.connect()
    await MemoryDatabaseManager.ensure_indexes(manager.get_database())
    _install_memory_manager(monkeypatch, manager)
    try:
        yield manager
    finally:
        await manager.disconnect()


@pytest.fixture()
async def disconnected_db(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Any]:
    """A database manager that is *not* connected.

    Used to prove that the API answers ``503`` instead of pretending to work.
    """
    from app.database.memory import MemoryDatabaseManager

    manager = MemoryDatabaseManager()
    # Deliberately not calling connect() - the manager stays offline.
    _install_memory_manager(monkeypatch, manager)
    try:
        yield manager
    finally:
        await manager.disconnect()


@pytest.fixture()
async def client(memory_db: Any) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client bound to the FastAPI application."""
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=True,
    ) as http_client:
        yield http_client


@pytest.fixture()
async def account(client: httpx.AsyncClient) -> Account:
    """A registered, signed-in standard user."""
    payload = await register_user(client)
    return Account.from_payload(payload, DEFAULT_PASSWORD)


@pytest.fixture()
async def other_account(client: httpx.AsyncClient) -> Account:
    """A second registered user - used for ownership tests."""
    payload = await register_user(
        client, email="neighbour@example.com", name="Neighbour Farmer"
    )
    return Account.from_payload(payload, DEFAULT_PASSWORD)


@pytest.fixture()
async def admin_account(
    client: httpx.AsyncClient, memory_db: Any
) -> Account:
    """A user whose role has been promoted to ``admin``."""
    payload = await register_user(
        client, email="admin@example.com", name="Site Admin"
    )
    users = memory_db.get_database()["users"]
    await users.update_one(
        {"email": "admin@example.com"}, {"$set": {"role": "admin"}}
    )
    return Account.from_payload(payload, DEFAULT_PASSWORD)


# ---------------------------------------------------------------------------
# Model fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def empty_model_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the model registry at an empty directory.

    Every model then reports itself as *not trained*, which is exactly the
    state a freshly cloned repository is in.  Used to prove that the API
    answers ``503`` instead of returning a fabricated prediction.
    """
    from ml.model_registry import registry

    monkeypatch.setattr(registry, "_model_dir", tmp_path)
    registry._reset()
    try:
        yield tmp_path
    finally:
        registry._reset()


# ---------------------------------------------------------------------------
# Image fixtures
# ---------------------------------------------------------------------------
def make_image_bytes(
    *, fmt: str = "PNG", size: tuple[int, int] = (256, 256), color: str = "green"
) -> bytes:
    """Render a small in-memory image for the upload tests."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture()
def leaf_image_bytes() -> bytes:
    """A valid PNG image that passes every validation rule."""
    return make_image_bytes(fmt="PNG", size=(256, 256))


@pytest.fixture()
def leaf_jpeg_bytes() -> bytes:
    """A valid JPEG image that passes every validation rule."""
    return make_image_bytes(fmt="JPEG", size=(300, 220), color="olive")


@pytest.fixture()
def tiny_image_bytes() -> bytes:
    """An image below the minimum accepted dimension."""
    return make_image_bytes(fmt="PNG", size=(16, 16))


@pytest.fixture()
def gif_image_bytes() -> bytes:
    """A GIF - a real image, but in a format the API deliberately rejects."""
    return make_image_bytes(fmt="GIF", size=(128, 128))


@pytest.fixture()
def empty_model_registry_status() -> Iterator[dict[str, Any]]:
    """Snapshot of the registry status with no models installed."""
    from ml.model_registry import registry

    status = registry.all_status()
    yield status
