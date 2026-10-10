from datetime import UTC, datetime

from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.models.email_verification import EmailVerification
from app.models.user import User
from tests.conftest import PASSWORD


async def _signup(
    client, email="new@example.com", password="validpass123", name="New User"
):
    return await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": password, "name": name}
    )


async def test_signup_login_and_me(client):
    resp = await _signup(client, email="New@Example.com")
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == "new@example.com"  # normalized
    assert body["user"]["email_verified"] is False

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "NEW@example.com", "password": "validpass123"},
    )
    assert login.status_code == 200
    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["name"] == "New User"


async def test_signup_duplicate_email_conflicts(client):
    assert (await _signup(client)).status_code == 201
    assert (await _signup(client)).status_code == 409


async def test_signup_validation(client):
    assert (await _signup(client, password="short")).status_code == 422
    assert (await _signup(client, name="   ")).status_code == 422
    assert (await _signup(client, email="not-an-email")).status_code == 422


async def test_login_wrong_password(client, make_user):
    user = await make_user(email="a@example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.user.email, "password": "wrong-password"},
    )
    assert resp.status_code == 401
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert unknown.status_code == 401
    assert unknown.json() == resp.json()  # no account enumeration


async def test_banned_user_cannot_login(client, make_user):
    user = await make_user(banned_at=datetime.now(UTC))
    resp = await client.post(
        "/api/v1/auth/login", json={"email": user.user.email, "password": PASSWORD}
    )
    assert resp.status_code == 403


async def test_refresh_rotates_tokens(client):
    tokens = (await _signup(client)).json()
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200
    assert resp.json()["refresh_token"] != tokens["refresh_token"]


async def test_refresh_token_reuse_revokes_all_sessions(client):
    first = (await _signup(client)).json()["refresh_token"]
    second = (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    ).json()["refresh_token"]
    # Replaying the already-rotated token is treated as theft...
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401
    # ...which also kills the legitimate, newer session.
    legit = await client.post("/api/v1/auth/refresh", json={"refresh_token": second})
    assert legit.status_code == 401


async def test_logout_revokes_refresh_token(client):
    tokens = (await _signup(client)).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )
    assert resp.status_code == 204
    again = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert again.status_code == 401


async def test_verify_email(client):
    await _signup(client)
    async with AsyncSessionLocal() as db:
        code = (
            await db.execute(
                select(EmailVerification.code)
                .join(User, User.id == EmailVerification.user_id)
                .where(User.email == "new@example.com")
            )
        ).scalar_one()

    wrong = "000000" if code != "000000" else "111111"
    bad = await client.post(
        "/api/v1/auth/verify-email", json={"email": "new@example.com", "code": wrong}
    )
    assert bad.status_code == 400

    ok = await client.post(
        "/api/v1/auth/verify-email", json={"email": "new@example.com", "code": code}
    )
    assert ok.status_code == 200 and ok.json() == {"verified": True}
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == "new@example.com"))
        ).scalar_one()
        assert user.email_verified


async def test_resend_verification_invalidates_old_code(client):
    tokens = (await _signup(client)).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (
        await client.post("/api/v1/auth/resend-verification", headers=headers)
    ).status_code == 204
    async with AsyncSessionLocal() as db:
        active = (
            (
                await db.execute(
                    select(EmailVerification).where(EmailVerification.used_at.is_(None))
                )
            )
            .scalars()
            .all()
        )
    assert len(active) == 1


async def test_deleted_account_cannot_refresh(client):
    tokens = (await _signup(client)).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.delete("/api/v1/users/me", headers=headers)).status_code == 204
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 401


async def test_protected_route_requires_token(client):
    assert (await client.get("/api/v1/users/me")).status_code == 401
    bad = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer junk"})
    assert bad.status_code == 401


async def test_banned_user_cannot_refresh(client):
    tokens = (await _signup(client)).json()
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).values(banned_at=datetime.now(UTC)))
        await db.commit()
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 401


async def test_health(client):
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    ready = await client.get("/readyz")
    assert ready.json()["database"] == "ok"
