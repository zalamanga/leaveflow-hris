import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from app.config import Settings
from app.db import Database
from app.main import create_app
from app.models import AnnualGrant, Base, User
from app.security import hash_password

PASSWORD = "Tests-Only-LeaveFlow42!"
ORIGIN = "http://testserver"


@dataclass
class Clock:
    now: datetime = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


class Actor:
    def __init__(self, app, email):
        self.client = TestClient(app)
        response = self.client.post("/api/auth/login", json={"email": email, "password": PASSWORD}, headers={"Origin": ORIGIN})
        assert response.status_code == 200, response.text
        self.auth = response.json()
        self.user = self.auth["user"]
        self.csrf = self.auth["csrf_token"]

    def get(self, path, **kwargs):
        return self.client.get(path, **kwargs)

    def post(self, path, body=None, **kwargs):
        headers = {"Origin": ORIGIN, "X-CSRF-Token": self.csrf}
        headers.update(kwargs.pop("headers", {}))
        return self.client.post(path, json=body, headers=headers, **kwargs)


def create_leave(actor, **overrides):
    grant = actor.get("/api/leave/balance?year=2026").json()
    payload = {"start_date": "2026-11-02", "end_date": "2026-11-04", "reason": "Family time arranged in advance", "expected_version": grant["version"]}
    payload.update(overrides)
    response = actor.post("/api/leave/requests", payload)
    assert response.status_code == 201, response.text
    return response.json()


def change(actor, request, action, **fields):
    response = actor.post(f"/api/leave/requests/{request['id']}/{action}", {"expected_version": request["version"], **fields})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["version"] == request["version"] + 1
    return result


@pytest.fixture(scope="session")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def world(tmp_path, password_hash):
    url = os.getenv("APP_TEST_DATABASE_URL")
    schema, admin = None, None
    if url:
        if not url.startswith("postgresql"):
            pytest.fail("APP_TEST_DATABASE_URL must be an isolated PostgreSQL test database")
        schema = "leaveflow_test_" + uuid.uuid4().hex
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    else:
        url = f"sqlite+pysqlite:///{(tmp_path / 'leaveflow.sqlite3').as_posix()}"
    database = Database(url)
    if schema:
        @event.listens_for(database.engine, "connect")
        def search_path(connection, record):
            previous = connection.autocommit
            connection.autocommit = True
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'SET search_path TO "{schema}"')
            finally:
                connection.autocommit = previous
    Base.metadata.create_all(database.engine)
    clock = Clock()
    settings = Settings(database_url=url, allowed_origins=(ORIGIN,), cookie_secure=False)
    app = create_app(settings=settings, database=database, clock=clock)
    with database.session_factory.begin() as db:
        manager = User(email="manager@test.test", name="Manager A", role="manager", password_hash=password_hash)
        manager2 = User(email="manager2@test.test", name="Manager B", role="manager", password_hash=password_hash)
        db.add_all([manager, manager2]); db.flush()
        db.add_all([User(email="employee@test.test", name="Employee A", role="employee", manager_id=manager.id, password_hash=password_hash), User(email="colleague@test.test", name="Employee B", role="employee", manager_id=manager.id, password_hash=password_hash), User(email="second@test.test", name="Employee C", role="employee", manager_id=manager2.id, password_hash=password_hash)])
        db.flush()
        for user in db.query(User).filter(User.role == "employee"):
            for year in (2026, 2027):
                db.add(AnnualGrant(employee_id=user.id, year=year, days=12, version=1))
    actors = {key: Actor(app, f"{key}@test.test") for key in ("manager", "manager2", "employee", "colleague", "second")}
    yield SimpleNamespace(app=app, db=database, clock=clock, settings=settings, **actors)
    for actor in actors.values():
        actor.client.close()
    database.dispose()
    if schema:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
