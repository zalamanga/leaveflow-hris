from datetime import date, datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def utcnow():
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Timestamps must be timezone-aware")
            return value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('employee','manager')", name="ck_user_role"), CheckConstraint("manager_id IS NULL OR manager_id <> id", name="ck_user_no_self_manager"))
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    user: Mapped[User] = relationship()


class AnnualGrant(Base):
    __tablename__ = "annual_grants"
    __table_args__ = (UniqueConstraint("employee_id", "year", name="uq_grant_employee_year"), CheckConstraint("days >= 0 AND days <= 366", name="ck_grant_days"), CheckConstraint("year >= 2000 AND year <= 2200", name="ck_grant_year"), CheckConstraint("version >= 1", name="ck_grant_version"))
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    days: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class CompanyHoliday(Base):
    __tablename__ = "company_holidays"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    __table_args__ = (CheckConstraint("status IN ('pending','approved','rejected','withdrawn','cancelled')", name="ck_leave_status"), CheckConstraint("units > 0 AND units <= 366", name="ck_leave_units"), CheckConstraint("end_date >= start_date", name="ck_leave_dates"), CheckConstraint("version >= 1", name="ck_leave_version"), Index("ix_leave_employee_status_dates", "employee_id", "status", "start_date", "end_date"))
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    working_days: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    employee: Mapped[User] = relationship(foreign_keys=[employee_id])
    events: Mapped[list["AuditEvent"]] = relationship(order_by="AuditEvent.id", cascade="all, delete-orphan")
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("leave_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    actor: Mapped[User] = relationship()


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)


class SeedMarker(Base):
    __tablename__ = "seed_markers"
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
