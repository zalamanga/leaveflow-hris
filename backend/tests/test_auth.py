from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.config import Settings
from app.models import Session, User
from app.security import token_hash
from conftest import ORIGIN, PASSWORD


def test_session_token_is_opaque_hashed_and_unique_cookie(world):
    cookie = world.employee.client.cookies.get("leaveflow_session")
    with world.db.session_factory() as db:
        row = db.scalar(select(Session).where(Session.token_hash == token_hash(cookie)))
        assert row.token_hash != cookie
        assert row.expires_at - row.created_at == timedelta(hours=24)
    assert world.employee.get("/api/auth/me").json()["user"]["role"] == "employee"


def test_unauthenticated_and_bad_login(world):
    with TestClient(world.app) as client:
        assert client.get("/api/leave/requests?year=2026").status_code == 401
        assert client.post("/api/auth/login", json={"email": "missing@test.test", "password": PASSWORD}).status_code == 401


def test_expired_or_inactive_session(world):
    world.clock.advance(hours=25)
    assert world.employee.get("/api/auth/me").status_code == 401
    with world.db.session_factory.begin() as db:
        db.get(User, world.colleague.user["id"]).is_active = False
    assert world.colleague.get("/api/auth/me").status_code == 401


def test_csrf_origin_and_content_guard(world):
    assert world.employee.client.post("/api/auth/logout", headers={"Origin": ORIGIN}).status_code == 403
    assert world.employee.post("/api/auth/logout", headers={"Origin": "https://bad.test"}).status_code == 403
    assert world.employee.post("/api/auth/logout", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert world.employee.client.post("/api/auth/login", content="bad", headers={"Content-Type": "text/plain"}).status_code == 415
    assert world.employee.client.post("/api/auth/login", content="x" * 65537, headers={"Content-Type": "application/json"}).status_code == 413


def test_logout_revokes_session(world):
    assert world.employee.post("/api/auth/logout").status_code == 204
    assert world.employee.get("/api/auth/me").status_code == 401


def test_login_cookie_flags_and_rotation(world):
    old = world.employee.client.cookies.get("leaveflow_session")
    response = world.employee.client.post("/api/auth/login", json={"email": "employee@test.test", "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/api" in cookie
    with world.db.session_factory() as db:
        assert db.scalar(select(Session.id).where(Session.token_hash == token_hash(old))) is None


def test_login_email_quota_and_window_reset(world):
    with TestClient(world.app) as client:
        for _ in range(8):
            assert client.post("/api/auth/login", json={"email": "unknown@test.test", "password": PASSWORD}).status_code == 401
        response = client.post("/api/auth/login", json={"email": "unknown@test.test", "password": PASSWORD})
        assert response.status_code == 429 and int(response.headers["retry-after"]) > 0
        world.clock.advance(minutes=16)
        assert client.post("/api/auth/login", json={"email": "unknown@test.test", "password": PASSWORD}).status_code == 401


def test_settings_reject_wildcard():
    with pytest.raises(ValueError):
        Settings(allowed_origins=("*",))


def test_peer_quota_spans_distinct_email_addresses(world):
    from dataclasses import replace
    from fastapi import HTTPException
    from app.main import consume_login_attempt
    settings = replace(world.settings, login_ip_limit=2)
    with world.db.session_factory() as db:
        consume_login_attempt(db, "isolated-test-peer", "one@test.test", world.clock(), settings)
        consume_login_attempt(db, "isolated-test-peer", "two@test.test", world.clock(), settings)
        with pytest.raises(HTTPException) as result:
            consume_login_attempt(db, "isolated-test-peer", "three@test.test", world.clock(), settings)
        assert result.value.status_code == 429


@pytest.mark.parametrize("email", ["a@", "a@domain", "a b@example.test", "a@@example.test"])
def test_email_validator_is_shared_by_api_and_account_cli(email):
    from pydantic import ValidationError
    from app.schemas import Login, canonical_email
    with pytest.raises(ValueError):
        canonical_email(email)
    with pytest.raises(ValidationError):
        Login(email=email, password=PASSWORD)
