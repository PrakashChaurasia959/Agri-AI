"""Authentication, session and password-management tests."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import DEFAULT_PASSWORD, Account, csrf_headers, register_user

PREFIX = "/api/v1/auth"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
async def test_register_creates_the_account_and_returns_a_token(client: httpx.AsyncClient):
    response = await client.post(
        f"{PREFIX}/register",
        json={
            "name": "Ananya Sharma",
            "email": "ananya@example.com",
            "password": "StrongPass123",
            "location": "Pune, Maharashtra",
            "primary_crops": ["rice", "wheat"],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0
    assert body["user"]["email"] == "ananya@example.com"
    assert body["user"]["name"] == "Ananya Sharma"
    assert body["user"]["role"] == "user"
    # The password hash must never leak through the API.
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


async def test_register_normalises_the_email_address(client: httpx.AsyncClient):
    response = await client.post(
        f"{PREFIX}/register",
        json={
            "name": "Case Test",
            "email": "  Mixed.Case@Example.COM ",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["user"]["email"] == "mixed.case@example.com"


async def test_register_rejects_a_duplicate_email(client: httpx.AsyncClient):
    payload = {
        "name": "First Farmer",
        "email": "duplicate@example.com",
        "password": "StrongPass123",
    }
    first = await client.post(f"{PREFIX}/register", json=payload)
    assert first.status_code == 201

    second = await client.post(f"{PREFIX}/register", json=payload)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"].lower()


@pytest.mark.parametrize(
    "password",
    ["short1", "alllettersonly", "12345678"],
)
async def test_register_rejects_weak_passwords(
    client: httpx.AsyncClient, password: str
):
    response = await client.post(
        f"{PREFIX}/register",
        json={
            "name": "Weak Password",
            "email": "weak@example.com",
            "password": password,
        },
    )
    assert response.status_code == 422
    assert "password" in response.json()["field_errors"]


async def test_register_rejects_an_invalid_email(client: httpx.AsyncClient):
    response = await client.post(
        f"{PREFIX}/register",
        json={"name": "Bad Email", "email": "not-an-email", "password": "StrongPass123"},
    )
    assert response.status_code == 422
    assert "email" in response.json()["field_errors"]


async def test_register_rejects_a_blank_name(client: httpx.AsyncClient):
    response = await client.post(
        f"{PREFIX}/register",
        json={"name": "   ", "email": "blank@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 422


async def test_register_never_promotes_the_first_user_to_admin(
    client: httpx.AsyncClient, memory_db
):
    """A public sign-up must never be able to escalate its own privileges."""
    payload = await register_user(client, email="first@example.com")

    assert payload["user"]["role"] == "user"

    users = memory_db.get_database()["users"]
    document = await users.find_one({"email": "first@example.com"})
    assert document is not None
    assert document["role"] == "user"


# ---------------------------------------------------------------------------
# Password storage
# ---------------------------------------------------------------------------
async def test_password_is_stored_as_an_argon2id_hash(
    client: httpx.AsyncClient, memory_db
):
    await register_user(client, email="hashed@example.com", password="SuperSecret9")

    users = memory_db.get_database()["users"]
    document = await users.find_one({"email": "hashed@example.com"})

    assert document is not None
    stored = document["password_hash"]
    assert stored.startswith("$argon2id$")
    assert "SuperSecret9" not in stored
    assert len(stored) > 40


async def test_two_accounts_with_the_same_password_get_different_hashes(
    client: httpx.AsyncClient, memory_db
):
    await register_user(client, email="one@example.com", password="SamePassword9")
    await register_user(client, email="two@example.com", password="SamePassword9")

    users = memory_db.get_database()["users"]
    first = await users.find_one({"email": "one@example.com"})
    second = await users.find_one({"email": "two@example.com"})

    assert first is not None and second is not None
    # Argon2 salts every hash, so identical passwords must not collide.
    assert first["password_hash"] != second["password_hash"]


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
async def test_login_with_valid_credentials_returns_a_token(client: httpx.AsyncClient):
    await register_user(client, email="login@example.com", password="StrongPass123")

    response = await client.post(
        f"{PREFIX}/login",
        json={"email": "login@example.com", "password": "StrongPass123"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "login@example.com"


async def test_login_with_a_wrong_password_is_rejected(client: httpx.AsyncClient):
    await register_user(client, email="wrongpw@example.com", password="StrongPass123")

    response = await client.post(
        f"{PREFIX}/login",
        json={"email": "wrongpw@example.com", "password": "WrongPassword123"},
    )

    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


async def test_login_with_an_unknown_email_is_rejected(client: httpx.AsyncClient):
    response = await client.post(
        f"{PREFIX}/login",
        json={"email": "nobody@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 401


async def test_login_error_message_does_not_reveal_whether_the_account_exists(
    client: httpx.AsyncClient,
):
    """The same message is returned for both failure modes."""
    await register_user(client, email="exists@example.com", password="StrongPass123")

    unknown = await client.post(
        f"{PREFIX}/login",
        json={"email": "unknown@example.com", "password": "StrongPass123"},
    )
    wrong = await client.post(
        f"{PREFIX}/login",
        json={"email": "exists@example.com", "password": "Nope123456"},
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


async def test_login_sets_the_expected_cookies(client: httpx.AsyncClient):
    await register_user(client, email="cookie@example.com", password="StrongPass123")
    client.cookies.clear()

    response = await client.post(
        f"{PREFIX}/login",
        json={"email": "cookie@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 200

    set_cookies = response.headers.get_list("set-cookie")
    joined = " | ".join(set_cookies)

    # The access token must be unreadable from JavaScript.
    assert "agrivision_token=" in joined
    access_cookie = next(c for c in set_cookies if c.startswith("agrivision_token="))
    assert "HttpOnly" in access_cookie

    # The refresh cookie is scoped to the auth routes only.
    refresh_cookie = next(c for c in set_cookies if c.startswith("agrivision_refresh="))
    assert "HttpOnly" in refresh_cookie
    assert "Path=/api/v1/auth" in refresh_cookie

    # The CSRF cookie is deliberately readable.
    csrf_cookie = next(c for c in set_cookies if c.startswith("agrivision_csrf="))
    assert "HttpOnly" not in csrf_cookie


async def test_login_records_the_last_login_timestamp(
    client: httpx.AsyncClient, memory_db
):
    await register_user(client, email="stamp@example.com", password="StrongPass123")

    response = await client.post(
        f"{PREFIX}/login",
        json={"email": "stamp@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 200

    users = memory_db.get_database()["users"]
    document = await users.find_one({"email": "stamp@example.com"})
    assert document is not None
    assert document["last_login_at"] is not None


# ---------------------------------------------------------------------------
# Session handling
# ---------------------------------------------------------------------------
async def test_me_requires_authentication(client: httpx.AsyncClient):
    response = await client.get(f"{PREFIX}/me")
    assert response.status_code == 401
    assert response.json()["detail"]


async def test_me_returns_the_profile_for_a_bearer_token(
    client: httpx.AsyncClient, account: Account
):
    response = await client.get(f"{PREFIX}/me", headers=account.headers)
    assert response.status_code == 200
    assert response.json()["email"] == account.email
    assert response.json()["id"] == account.id


async def test_me_works_with_the_session_cookie(client: httpx.AsyncClient, account: Account):
    # ``account`` registered through this client, so the cookies are present.
    response = await client.get(f"{PREFIX}/me")
    assert response.status_code == 200
    assert response.json()["email"] == account.email


async def test_refresh_requires_a_refresh_cookie(client: httpx.AsyncClient):
    client.cookies.clear()
    response = await client.post(f"{PREFIX}/refresh")
    assert response.status_code == 401


async def test_refresh_issues_a_new_access_token(client: httpx.AsyncClient, account: Account):
    response = await client.post(f"{PREFIX}/refresh")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == account.email


async def test_logout_clears_the_session(client: httpx.AsyncClient, account: Account):
    response = await client.post(f"{PREFIX}/logout", headers=csrf_headers(client))
    assert response.status_code == 200
    assert response.json()["success"] is True

    cleared = " | ".join(response.headers.get_list("set-cookie"))
    assert "agrivision_token=" in cleared
    # The cookie is expired rather than merely blanked.
    assert "Max-Age=0" in cleared or "Expires=Thu, 01 Jan 1970" in cleared


async def test_logout_requires_the_csrf_token_when_using_the_cookie(
    client: httpx.AsyncClient, account: Account
):
    """A cookie-authenticated mutation without the CSRF header is rejected."""
    client.cookies.delete("agrivision_csrf")

    response = await client.post(f"{PREFIX}/logout")
    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


async def test_a_mismatched_csrf_token_is_rejected(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{PREFIX}/logout", headers={"X-CSRF-Token": "definitely-not-the-token"}
    )
    assert response.status_code == 403


async def test_a_bearer_token_does_not_need_the_csrf_header(
    client: httpx.AsyncClient, account: Account
):
    """Bearer clients are not vulnerable to CSRF, so no header is required."""
    response = await client.post(f"{PREFIX}/logout", headers=account.headers)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Profile management
# ---------------------------------------------------------------------------
async def test_update_profile_changes_the_stored_fields(
    client: httpx.AsyncClient, account: Account, memory_db
):
    response = await client.patch(
        f"{PREFIX}/me",
        headers=account.headers,
        json={
            "name": "Ananya S.",
            "location": "Nashik, Maharashtra",
            "farm_size_hectares": 12.5,
            "primary_crops": ["sugarcane"],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Ananya S."
    assert body["location"] == "Nashik, Maharashtra"
    assert body["farm_size_hectares"] == 12.5

    users = memory_db.get_database()["users"]
    document = await users.find_one({"email": account.email})
    assert document is not None
    assert document["farm_size_hectares"] == 12.5


async def test_update_profile_with_no_fields_is_rejected(
    client: httpx.AsyncClient, account: Account
):
    response = await client.patch(f"{PREFIX}/me", headers=account.headers, json={})
    assert response.status_code == 400


async def test_update_profile_rejects_a_negative_farm_size(
    client: httpx.AsyncClient, account: Account
):
    response = await client.patch(
        f"{PREFIX}/me", headers=account.headers, json={"farm_size_hectares": -5}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------
async def test_change_password_then_login_with_the_new_one(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{PREFIX}/change-password",
        headers=account.headers,
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": "BrandNewPass456",
        },
    )
    assert response.status_code == 200, response.text

    old_login = await client.post(
        f"{PREFIX}/login",
        json={"email": account.email, "password": DEFAULT_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        f"{PREFIX}/login",
        json={"email": account.email, "password": "BrandNewPass456"},
    )
    assert new_login.status_code == 200


async def test_change_password_rejects_a_wrong_current_password(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{PREFIX}/change-password",
        headers=account.headers,
        json={
            "current_password": "NotThePassword1",
            "new_password": "BrandNewPass456",
        },
    )
    assert response.status_code == 400
    assert "current password" in response.json()["detail"].lower()


async def test_change_password_rejects_reusing_the_same_password(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{PREFIX}/change-password",
        headers=account.headers,
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": DEFAULT_PASSWORD,
        },
    )
    assert response.status_code == 400


async def test_change_password_rejects_a_weak_new_password(
    client: httpx.AsyncClient, account: Account
):
    response = await client.post(
        f"{PREFIX}/change-password",
        headers=account.headers,
        json={"current_password": DEFAULT_PASSWORD, "new_password": "abc"},
    )
    assert response.status_code == 422
