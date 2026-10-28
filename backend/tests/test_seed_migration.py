from datetime import datetime, timezone
import pytest
from sqlalchemy import func, inspect, select
from app.cli import init_db
from app.db import Database
from app.models import AnnualGrant, Base, LeaveRequest, SeedMarker, User
from app.seed import seed_demo


def test_alembic_upgrade_is_repeatable(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'migration.sqlite3').as_posix()}"
    init_db(url); init_db(url)
    db = Database(url)
    assert set(Base.metadata.tables).issubset(inspect(db.engine).get_table_names())
    db.dispose()


def test_seed_is_explicit_atomic_and_never_overwrites(tmp_path):
    db = Database(f"sqlite+pysqlite:///{(tmp_path / 'seed.sqlite3').as_posix()}")
    Base.metadata.create_all(db.engine)
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        with db.session_factory.begin() as session:
            seed_demo(session, "short", now)
    with db.session_factory.begin() as session:
        assert seed_demo(session, "SyntheticOnly-LeaveFlow42!", now)
    with db.session_factory.begin() as session:
        row = session.scalar(select(User).where(User.email == "employee@leaveflow.test"))
        row.name = "User modified name"
        assert not seed_demo(session, "AnotherSyntheticPassword42!", now)
    with db.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 5
        assert session.scalar(select(func.count()).select_from(AnnualGrant)) == 6
        assert session.scalar(select(func.count()).select_from(LeaveRequest)) == 3
        assert session.scalar(select(User.name).where(User.email == "employee@leaveflow.test")) == "User modified name"
        assert session.get(SeedMarker, "leaveflow-training-v1")
    db.dispose()
