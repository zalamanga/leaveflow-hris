import csv
import io
import secrets
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as OrmSession, joinedload
from sqlalchemy.orm.exc import StaleDataError
from .config import Settings
from .db import Database
from .models import AnnualGrant, AuditEvent, LeaveRequest, RateLimitBucket, Session, User, utcnow
from .policy import POLICY, estimate, office_today
from .schemas import Decision, Login, NewLeave, Version
from .security import new_token, token_hash, verify_password

COOKIE = "leaveflow_session"

def get_db(request: Request):
    with request.app.state.database.session_factory() as db:
        yield db


DB = Annotated[OrmSession, Depends(get_db)]


def get_auth(request: Request, db: DB):
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 128:
        raise HTTPException(401, "Sign in to continue")
    session = db.scalar(select(Session).where(Session.token_hash == token_hash(token)))
    if session is None or session.expires_at <= request.app.state.clock() or not session.user.is_active:
        raise HTTPException(401, "Session expired; sign in again")
    return session


Auth = Annotated[Session, Depends(get_auth)]


def mutation_auth(request: Request, auth: Auth):
    csrf = request.headers.get("x-csrf-token", "")
    if not csrf or not secrets.compare_digest(csrf.encode("utf-8"), auth.csrf_token.encode("ascii")):
        raise HTTPException(403, "Invalid CSRF token; refresh your session")
    return auth


MutationAuth = Annotated[Session, Depends(mutation_auth)]


def consume_login_attempt(db: OrmSession, ip: str, email: str, now: datetime, settings: Settings):
    seconds = settings.login_window_seconds
    start = datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, tz=timezone.utc)
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    counts = []
    for scope, identity in (("ip", ip), ("email", email)):
        key = token_hash(f"{scope}:{identity}")
        statement = insert(RateLimitBucket).values(key=key, window_start=start, attempts=1)
        statement = statement.on_conflict_do_update(index_elements=[RateLimitBucket.key], set_={
            "window_start": start,
            "attempts": case((RateLimitBucket.window_start == start, RateLimitBucket.attempts + 1), else_=1),
        }).returning(RateLimitBucket.attempts)
        counts.append(db.execute(statement).scalar_one())
    db.execute(delete(RateLimitBucket).where(RateLimitBucket.window_start < now - timedelta(days=2)))
    db.commit()
    if counts[0] > settings.login_ip_limit or counts[1] > settings.login_limit:
        retry = max(1, int((start + timedelta(seconds=seconds) - now).total_seconds()))
        raise HTTPException(429, "Too many sign-in attempts. Try again later", headers={"Retry-After": str(retry)})


def csv_cell(value):
    string = str(value) if value is not None else ""
    if string.lstrip().startswith(("=", "+", "-", "@")) or string.startswith(("\t", "\r", "\n")):
        return "'" + string
    return string


def iso(value):
    return value.isoformat() if value is not None else None


def session_response(auth, settings):
    user = auth.user
    return {"user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "manager_id": user.manager_id}, "csrf_token": auth.csrf_token, "demo_mode": settings.demo_mode}


def require_employee(user):
    if user.role != "employee":
        raise HTTPException(403, "Gunakan akun karyawan untuk mengajukan cuti")


def require_manager(user):
    if user.role != "manager":
        raise HTTPException(403, "Akun manajer diperlukan")


def visibility(user):
    if user.role == "employee":
        return LeaveRequest.employee_id == user.id
    return LeaveRequest.employee_id.in_(select(User.id).where(User.manager_id == user.id, User.role == "employee"))


def balance(db, employee_id, year, grant=None):
    grant = grant or db.scalar(select(AnnualGrant).where(AnnualGrant.employee_id == employee_id, AnnualGrant.year == year))
    rows = dict(db.execute(select(LeaveRequest.status, func.sum(LeaveRequest.units)).where(LeaveRequest.employee_id == employee_id, LeaveRequest.year == year, LeaveRequest.status.in_(("pending", "approved"))).group_by(LeaveRequest.status)).all())
    approved, pending = int(rows.get("approved", 0)), int(rows.get("pending", 0))
    granted = grant.days if grant else 0
    return {"year": year, "granted": granted, "approved": approved, "pending": pending, "available": granted - approved - pending, "version": grant.version if grant else None, "configured": grant is not None, "policy": POLICY}


def summary(row):
    return {"id": row.id, "key": f"LV-{row.id:04d}", "employee": {"id": row.employee_id, "name": row.employee.name}, "year": row.year, "start_date": iso(row.start_date), "end_date": iso(row.end_date), "units": row.units, "status": row.status, "version": row.version, "created_at": iso(row.created_at), "updated_at": iso(row.updated_at)}


def detail(row):
    return {**summary(row), "reason": row.reason, "working_days": row.working_days, "policy_snapshot": row.policy_snapshot, "review_reason": row.review_reason, "reviewer_id": row.reviewer_id, "events": [{"id": item.id, "actor": item.actor.name, "kind": item.kind, "note": item.note, "created_at": iso(item.created_at)} for item in row.events]}


def load_request(db, request_id, user):
    row = db.scalar(select(LeaveRequest).where(LeaveRequest.id == request_id, visibility(user)))
    if row is None:
        raise HTTPException(404, "Permintaan tidak ditemukan")
    return row


def lock_account(db, employee_id, year):
    # All mutations use employee -> grant -> request, including independent creations.
    employee = db.scalar(select(User).where(User.id == employee_id).with_for_update().execution_options(populate_existing=True))
    grant = db.scalar(select(AnnualGrant).where(AnnualGrant.employee_id == employee_id, AnnualGrant.year == year).with_for_update().execution_options(populate_existing=True))
    if employee is None or not employee.is_active or employee.role != "employee":
        raise HTTPException(409, "Akun karyawan tidak aktif")
    if grant is None:
        raise HTTPException(422, "Kuota tahun ini belum dikonfigurasi. Hubungi administrator")
    return employee, grant


def locked_request(db, request_id, user, expected_version):
    identified = load_request(db, request_id, user)
    employee, grant = lock_account(db, identified.employee_id, identified.year)
    row = db.scalar(select(LeaveRequest).where(LeaveRequest.id == request_id, visibility(user)).with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, "Permintaan tidak ditemukan")
    if row.version != expected_version:
        raise HTTPException(409, "Permintaan telah berubah. Muat ulang sebelum mencoba lagi")
    return row, grant


def audit(db, row, actor, kind, note, now):
    db.add(AuditEvent(request_id=row.id, actor_id=actor.id, kind=kind, note=note, created_at=now))


def finish(db, row, grant, now):
    row.version += 1
    row.updated_at = now
    grant.version += 1
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(409, "Saldo atau permintaan berubah. Muat ulang sebelum mencoba lagi") from None
    except OperationalError as error:
        db.rollback()
        if db.bind.dialect.name == "sqlite" and "locked" in str(error).lower():
            raise HTTPException(409, "Permintaan sedang diperbarui. Muat ulang sebelum mencoba lagi") from None
        raise
    db.expire(row, ["events", "employee"])


def filters(user, q, status, year):
    clauses = [visibility(user), LeaveRequest.year == year]
    if status:
        clauses.append(LeaveRequest.status == status)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append(or_(LeaveRequest.reason.ilike(f"%{escaped}%", escape="\\"), LeaveRequest.employee_id.in_(select(User.id).where(User.name.ilike(f"%{escaped}%", escape="\\")))))
    return clauses


def create_app(settings: Settings | None = None, database: Database | None = None,
               clock: Callable[[], datetime] = utcnow):
    settings = settings or Settings()
    app = FastAPI(title="LeaveFlow API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.database = database or Database(settings.database_url)
    app.state.settings = settings
    app.state.clock = clock

    @app.middleware("http")
    async def request_guards(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin is not None and origin not in settings.allowed_origins:
                return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site requests are not allowed"}, status_code=403)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    return JSONResponse({"detail": "Request body exceeds 64 KiB"}, status_code=413)
            request._body = bytes(body)
            if body and request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                return JSONResponse({"detail": "Use application/json"}, status_code=415)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/health")
    def health(db: DB):
        try:
            db.execute(select(User.id).limit(1))
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ok"}

    @app.post("/api/auth/login")
    def login(payload: Login, request: Request, response: Response, db: DB):
        now = clock()
        email = payload.email.strip().lower()
        ip = request.client.host if request.client else "unknown"
        consume_login_attempt(db, ip, email, now, settings)
        user = db.scalar(select(User).where(User.email == email))
        if not verify_password(payload.password, user.password_hash if user else None) or not user or not user.is_active:
            raise HTTPException(401, "Email or password is incorrect")
        if request.cookies.get(COOKIE):
            db.execute(delete(Session).where(Session.token_hash == token_hash(request.cookies[COOKIE])))
        db.execute(delete(Session).where(Session.expires_at <= now))
        token = new_token()
        auth = Session(token_hash=token_hash(token), user_id=user.id, user=user, csrf_token=new_token(),
                       created_at=now, expires_at=now + timedelta(hours=settings.session_hours))
        db.add(auth)
        db.commit()
        response.set_cookie(COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="lax", path="/api",
                            max_age=settings.session_hours * 3600)
        return session_response(auth, settings)

    @app.get("/api/auth/me")
    def me(auth: Auth):
        return session_response(auth, settings)

    @app.post("/api/auth/logout", status_code=204)
    def logout(response: Response, auth: MutationAuth, db: DB):
        db.delete(auth)
        db.commit()
        response.delete_cookie(COOKIE, path="/api", secure=settings.cookie_secure, httponly=True, samesite="lax")

    @app.get("/api/leave/context")
    def context(auth: Auth):
        today = office_today(clock())
        return {"today": today.isoformat(), "year": today.year, "office_timezone": "Asia/Jakarta", "policy": POLICY}

    @app.get("/api/leave/balance")
    def my_balance(auth: Auth, db: DB, year: int = Query(ge=2000, le=2200)):
        require_employee(auth.user)
        return balance(db, auth.user_id, year)

    @app.get("/api/leave/estimate")
    def preview(auth: Auth, db: DB, start_date: date, end_date: date):
        require_employee(auth.user)
        return estimate(db, start_date, end_date, office_today(clock()))

    @app.get("/api/leave/requests")
    def requests(auth: Auth, db: DB, year: int = Query(ge=2000, le=2200), q: str = Query(default="", max_length=200), status: Literal["pending", "approved", "rejected", "withdrawn", "cancelled"] | None = None, page: int = Query(default=1, ge=1, le=100000), page_size: int = Query(default=20, ge=1, le=100)):
        clauses = filters(auth.user, q.strip(), status, year)
        total = db.scalar(select(func.count()).select_from(LeaveRequest).where(*clauses))
        rows = db.scalars(select(LeaveRequest).options(joinedload(LeaveRequest.employee)).where(*clauses).order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc()).offset((page-1)*page_size).limit(page_size))
        counts = dict(db.execute(select(LeaveRequest.status, func.count()).where(visibility(auth.user), LeaveRequest.year == year).group_by(LeaveRequest.status)).all())
        return {"items": [summary(row) for row in rows], "total": total, "page": page, "page_size": page_size, "counts": {key: counts.get(key, 0) for key in ("pending", "approved", "rejected", "withdrawn", "cancelled")}}

    @app.get("/api/leave/requests/export.csv")
    def export(auth: Auth, db: DB, year: int = Query(ge=2000, le=2200), q: str = Query(default="", max_length=200), status: Literal["pending", "approved", "rejected", "withdrawn", "cancelled"] | None = None):
        require_manager(auth.user)
        rows = list(db.scalars(select(LeaveRequest).options(joinedload(LeaveRequest.employee)).where(*filters(auth.user, q.strip(), status, year)).order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc()).limit(10001)))
        if len(rows) > 10000:
            raise HTTPException(422, "Ekspor melebihi 10000 baris; persempit filter")
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["reference", "employee", "start_date", "end_date", "working_days", "status"])
        for row in rows:
            writer.writerow([csv_cell(value) for value in (f"LV-{row.id:04d}", row.employee.name, row.start_date, row.end_date, row.units, row.status)])
        return Response("\ufeff" + buffer.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="leaveflow-requests.csv"'})

    @app.get("/api/leave/calendar")
    def calendar(auth: Auth, db: DB, year: int = Query(ge=2000, le=2200), month: int = Query(ge=1, le=12)):
        start = date(year, month, 1)
        end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        rows = list(db.scalars(select(LeaveRequest).options(joinedload(LeaveRequest.employee)).where(visibility(auth.user), LeaveRequest.status == "approved", LeaveRequest.start_date < end, LeaveRequest.end_date >= start).order_by(LeaveRequest.start_date, LeaveRequest.id).limit(1001)))
        if len(rows) > 1000:
            raise HTTPException(422, "Kalender melebihi 1000 cuti; hubungi administrator")
        return {"year": year, "month": month, "items": [{"id": row.id, "employee": {"id": row.employee_id, "name": row.employee.name}, "start_date": iso(row.start_date), "end_date": iso(row.end_date), "units": row.units, "working_days": row.working_days} for row in rows]}

    @app.post("/api/leave/requests", status_code=201)
    def create_leave(payload: NewLeave, auth: MutationAuth, db: DB):
        require_employee(auth.user)
        now = clock()
        _employee, grant = lock_account(db, auth.user_id, payload.start_date.year)
        if grant.version != payload.expected_version:
            raise HTTPException(409, "Saldo telah berubah. Muat ulang sebelum mengirim lagi")
        preview = estimate(db, payload.start_date, payload.end_date, office_today(now))
        overlap = db.scalar(select(LeaveRequest.id).where(LeaveRequest.employee_id == auth.user_id, LeaveRequest.status.in_(("pending", "approved")), LeaveRequest.start_date <= payload.end_date, LeaveRequest.end_date >= payload.start_date).limit(1))
        if overlap:
            raise HTTPException(409, "Rentang tanggal bertabrakan dengan permintaan aktif, termasuk akhir pekan di dalam rentang")
        available = balance(db, auth.user_id, payload.start_date.year, grant)["available"]
        if preview["units"] > available:
            raise HTTPException(422, "Saldo tersedia tidak cukup setelah reservasi permintaan menunggu")
        row = LeaveRequest(employee_id=auth.user_id, year=preview["year"], start_date=payload.start_date, end_date=payload.end_date, reason=payload.reason, working_days=preview["working_days"], policy_snapshot={**preview["policy"], "excluded_days": preview["excluded_days"]}, units=preview["units"], status="pending", version=1, created_at=now, updated_at=now)
        db.add(row)
        db.flush()
        audit(db, row, auth.user, "submitted", f"Mengajukan {row.units} hari kerja; saldo direservasi", now)
        grant.version += 1
        try:
            db.commit()
        except StaleDataError:
            db.rollback()
            raise HTTPException(409, "Saldo berubah. Muat ulang sebelum mengirim lagi") from None
        return detail(row)

    @app.get("/api/leave/requests/{request_id}")
    def request_detail(request_id: int, auth: Auth, db: DB):
        return detail(load_request(db, request_id, auth.user))

    @app.post("/api/leave/requests/{request_id}/withdraw")
    def withdraw(request_id: int, payload: Version, auth: MutationAuth, db: DB):
        require_employee(auth.user)
        row, grant = locked_request(db, request_id, auth.user, payload.expected_version)
        if row.status != "pending":
            raise HTTPException(409, "Hanya permintaan menunggu yang dapat ditarik")
        row.status = "withdrawn"
        now = clock()
        audit(db, row, auth.user, "withdrawn", "Karyawan menarik permintaan; reservasi saldo dilepas", now)
        finish(db, row, grant, now)
        return detail(row)

    def review(request_id, payload, auth, db, action):
        require_manager(auth.user)
        row, grant = locked_request(db, request_id, auth.user, payload.expected_version)
        if row.employee_id == auth.user_id:
            raise HTTPException(403, "Tidak dapat meninjau permintaan sendiri")
        expected_status = "approved" if action == "cancel" else "pending"
        if row.status != expected_status:
            raise HTTPException(409, "Status permintaan sudah berubah; muat ulang")
        if action in {"reject", "cancel"} and len(payload.reason.strip()) < 10:
            raise HTTPException(422, "Tuliskan alasan sedikitnya 10 karakter")
        row.status = {"approve": "approved", "reject": "rejected", "cancel": "cancelled"}[action]
        row.reviewer_id = auth.user_id
        row.review_reason = payload.reason.strip() or None
        now = clock()
        note = payload.reason.strip() or "Manajer menyetujui permintaan; reservasi menjadi penggunaan saldo"
        audit(db, row, auth.user, row.status, note, now)
        finish(db, row, grant, now)
        return detail(row)

    @app.post("/api/leave/requests/{request_id}/approve")
    def approve(request_id: int, payload: Decision, auth: MutationAuth, db: DB):
        return review(request_id, payload, auth, db, "approve")

    @app.post("/api/leave/requests/{request_id}/reject")
    def reject(request_id: int, payload: Decision, auth: MutationAuth, db: DB):
        return review(request_id, payload, auth, db, "reject")

    @app.post("/api/leave/requests/{request_id}/cancel")
    def cancel(request_id: int, payload: Decision, auth: MutationAuth, db: DB):
        return review(request_id, payload, auth, db, "cancel")

    return app


app = create_app()
