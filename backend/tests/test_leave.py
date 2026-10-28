from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.models import AnnualGrant, AuditEvent, CompanyHoliday, LeaveRequest, User
from conftest import Actor, ORIGIN, change, create_leave


def balance(world):
    response = world.employee.get("/api/leave/balance?year=2026")
    assert response.status_code == 200
    return response.json()


def test_reserve_approve_cancel_no_double_spend(world):
    row = create_leave(world.employee)
    current = balance(world)
    assert (current["available"], current["pending"], current["approved"]) == (9, 3, 0)
    row = change(world.manager, row, "approve")
    assert balance(world)["available"] == 9
    assert balance(world)["pending"] == 0
    assert balance(world)["approved"] == 3
    row = change(world.manager, row, "cancel", reason="Employee changed the travel plan")
    assert row["status"] == "cancelled"
    assert balance(world)["available"] == 12
    assert len(row["events"]) == 3


@pytest.mark.parametrize("action,actor", [("reject", "manager"), ("withdraw", "employee")])
def test_release_pending_reservation(world, action, actor):
    row = create_leave(world.employee)
    row = change(getattr(world, actor), row, action, **({"reason": "Team coverage cannot be arranged"} if action == "reject" else {}))
    assert row["status"] in {"withdrawn", "rejected"}
    assert balance(world)["available"] == 12
    assert len(row["events"]) == 2


@pytest.mark.parametrize("actor", ["colleague", "second", "manager2"])
def test_other_employee_or_team_details_and_mutation_hidden(world, actor):
    row = create_leave(world.employee)
    stranger = getattr(world, actor)
    assert stranger.get(f"/api/leave/requests/{row['id']}").status_code == 404
    endpoint = "approve" if "manager" in actor else "withdraw"
    assert stranger.post(f"/api/leave/requests/{row['id']}/{endpoint}", {"expected_version": 1}).status_code == 404


def test_team_scope_search_counts_export_and_calendar(world):
    row = create_leave(world.second, reason="Outside team secret reason")
    change(world.manager2, row, "approve")
    result = world.manager.get("/api/leave/requests?year=2026&q=Outside").json()
    assert result["items"] == [] and result["total"] == 0
    assert result["counts"]["approved"] == 0
    assert "Employee C" not in world.manager.get("/api/leave/requests/export.csv?year=2026").text
    assert world.manager.get("/api/leave/calendar?year=2026&month=11").json()["items"] == []


def test_employee_calendar_only_own_approved_and_no_private_fields(world):
    own = create_leave(world.employee)
    other = create_leave(world.colleague)
    change(world.manager, other, "approve")
    assert world.employee.get("/api/leave/calendar?year=2026&month=11").json()["items"] == []
    change(world.manager, own, "approve")
    rows = world.employee.get("/api/leave/calendar?year=2026&month=11").json()["items"]
    assert len(rows) == 1 and rows[0]["employee"]["id"] == world.employee.user["id"]
    assert not {"reason", "review_reason", "events"} & rows[0].keys()
    assert len(world.manager.get("/api/leave/calendar?year=2026&month=11").json()["items"]) == 2


def test_weekend_holiday_calculation_and_snapshot(world):
    with world.db.session_factory.begin() as db:
        db.add(CompanyHoliday(day=date(2026, 11, 4), label="Fictional training office day"))
    result = world.employee.get("/api/leave/estimate?start_date=2026-11-02&end_date=2026-11-08").json()
    assert result["units"] == 4
    assert len(result["excluded_days"]) == 3
    row = create_leave(world.employee, end_date="2026-11-08")
    assert row["units"] == 4
    assert "2026-11-04" not in row["working_days"]
    with world.db.session_factory.begin() as db:
        db.add(CompanyHoliday(day=date(2026, 11, 3), label="Later policy change"))
    assert world.employee.get(f"/api/leave/requests/{row['id']}").json()["units"] == 4


@pytest.mark.parametrize("start,end", [("2026-10-27", "2026-10-29"), ("2026-11-04", "2026-11-02"), ("2026-12-31", "2027-01-01"), ("2026-11-07", "2026-11-08")])
def test_invalid_dates_rejected_for_preview_and_create(world, start, end):
    assert world.employee.get(f"/api/leave/estimate?start_date={start}&end_date={end}").status_code == 422
    assert world.employee.post("/api/leave/requests", {"start_date": start, "end_date": end, "reason": "A sufficiently clear explanation", "expected_version": 1}).status_code == 422


def test_jakarta_office_date_boundary(world):
    world.clock.now = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
    assert world.employee.get("/api/leave/context").json()["today"] == "2026-10-29"
    assert world.employee.get("/api/leave/estimate?start_date=2026-10-28&end_date=2026-10-28").status_code == 422


def test_overlapping_ranges_include_weekend_and_release_after_withdraw(world):
    row = create_leave(world.employee, start_date="2026-11-06", end_date="2026-11-09")
    payload = {"start_date": "2026-11-07", "end_date": "2026-11-10", "reason": "An overlapping request across weekend", "expected_version": balance(world)["version"]}
    assert world.employee.post("/api/leave/requests", payload).status_code == 409
    change(world.employee, row, "withdraw")
    payload["expected_version"] = balance(world)["version"]
    assert world.employee.post("/api/leave/requests", payload).status_code == 201


def test_no_quota_audit_or_version_side_effect_when_insufficient(world):
    with world.db.session_factory.begin() as db:
        grant = db.scalar(select(AnnualGrant).where(AnnualGrant.employee_id == world.employee.user["id"], AnnualGrant.year == 2026))
        grant.days = 2
    response = world.employee.post("/api/leave/requests", {"start_date": "2026-11-02", "end_date": "2026-11-04", "reason": "Three working days needed", "expected_version": 1})
    assert response.status_code == 422
    with world.db.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(LeaveRequest)) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 0
    assert balance(world)["version"] == 1


def test_missing_grant_and_stale_balance_do_not_create(world):
    assert world.employee.post("/api/leave/requests", {"start_date": "2028-01-03", "end_date": "2028-01-03", "reason": "Future annual leave planned", "expected_version": 1}).status_code == 422
    create_leave(world.employee)
    assert world.employee.post("/api/leave/requests", {"start_date": "2026-11-09", "end_date": "2026-11-09", "reason": "A stale balance request", "expected_version": 1}).status_code == 409


@pytest.mark.parametrize("action", ["approve", "reject", "cancel"])
def test_employee_cannot_review(world, action):
    row = create_leave(world.employee)
    assert world.employee.post(f"/api/leave/requests/{row['id']}/{action}", {"expected_version": 1, "reason": "An explanation for this action"}).status_code == 403


def test_manager_cannot_create_or_withdraw_and_employee_cannot_export(world):
    assert world.manager.post("/api/leave/requests", {"start_date": "2026-11-02", "end_date": "2026-11-02", "reason": "Manager self leave attempted", "expected_version": 1}).status_code == 403
    row = create_leave(world.employee)
    assert world.manager.post(f"/api/leave/requests/{row['id']}/withdraw", {"expected_version": 1}).status_code == 403
    assert world.employee.get("/api/leave/requests/export.csv?year=2026").status_code == 403
    assert world.manager.get("/api/leave/balance?year=2026").status_code == 403


@pytest.mark.parametrize("action", ["reject", "cancel"])
def test_rejection_cancellation_reason_required(world, action):
    row = create_leave(world.employee)
    if action == "cancel":
        row = change(world.manager, row, "approve")
    response = world.manager.post(f"/api/leave/requests/{row['id']}/{action}", {"expected_version": row["version"], "reason": "short"})
    assert response.status_code == 422
    assert world.manager.get(f"/api/leave/requests/{row['id']}").json()["version"] == row["version"]


def test_stale_review_and_invalid_state_have_no_extra_audit(world):
    row = create_leave(world.employee)
    approved = change(world.manager, row, "approve")
    assert world.manager.post(f"/api/leave/requests/{row['id']}/reject", {"expected_version": row["version"], "reason": "Attempted stale rejection"}).status_code == 409
    assert world.employee.post(f"/api/leave/requests/{row['id']}/withdraw", {"expected_version": approved["version"]}).status_code == 409
    assert len(world.employee.get(f"/api/leave/requests/{row['id']}").json()["events"]) == 2


def test_audit_failure_rolls_back_status_and_balance(world, monkeypatch):
    import app.main as main
    row = create_leave(world.employee)
    def fail_audit(*args, **kwargs):
        raise RuntimeError("Injected audit persistence failure")
    monkeypatch.setattr(main, "audit", fail_audit)
    with pytest.raises(RuntimeError, match="Injected"):
        world.manager.post(f"/api/leave/requests/{row['id']}/approve", {"expected_version": 1})
    result = world.employee.get(f"/api/leave/requests/{row['id']}").json()
    assert result["status"] == "pending" and result["version"] == 1 and len(result["events"]) == 1
    assert balance(world)["pending"] == 3 and balance(world)["approved"] == 0


def test_csv_formula_neutralized(world):
    with world.db.session_factory.begin() as db:
        db.get(User, world.employee.user["id"]).name = " =HYPERLINK(test)"
    create_leave(world.employee)
    response = world.manager.get("/api/leave/requests/export.csv?year=2026")
    assert response.status_code == 200 and "' =HYPERLINK(test)" in response.text


def test_query_limits_and_pagination_latest_first(world):
    old = create_leave(world.employee)
    world.clock.advance(minutes=1)
    new = create_leave(world.employee, start_date="2026-11-09", end_date="2026-11-09")
    result = world.manager.get("/api/leave/requests?year=2026&page_size=1").json()
    assert result["total"] == 2 and result["items"][0]["id"] == new["id"]
    assert world.manager.get("/api/leave/requests?year=2026&page=2&page_size=1").json()["items"][0]["id"] == old["id"]
    assert world.manager.get("/api/leave/requests?year=2026&page_size=101").status_code == 422


def test_server_rejects_client_quota_or_identity_fields(world):
    body = {"start_date": "2026-11-02", "end_date": "2026-11-02", "reason": "Sufficient reason for request", "expected_version": 1, "units": 0, "employee_id": world.colleague.user["id"]}
    assert world.employee.post("/api/leave/requests", body).status_code == 422


@pytest.mark.parametrize("version", [True, False, 1.0, "1"])
def test_versions_require_actual_integer_json_values(world, version):
    body = {"start_date": "2026-11-02", "end_date": "2026-11-02", "reason": "Sufficient reason for request", "expected_version": version}
    assert world.employee.post("/api/leave/requests", body).status_code == 422
    row = create_leave(world.employee)
    assert world.manager.post(f"/api/leave/requests/{row['id']}/approve", {"expected_version": version}).status_code == 422
    assert world.employee.post(f"/api/leave/requests/{row['id']}/withdraw", {"expected_version": version}).status_code == 422


def test_postgresql_concurrent_reservations_one_winner(world):
    if world.db.engine.dialect.name != "postgresql":
        pytest.skip("Requires actual PostgreSQL row locks")
    with world.db.session_factory.begin() as db:
        db.scalar(select(AnnualGrant).where(AnnualGrant.employee_id == world.employee.user["id"], AnnualGrant.year == 2026)).days = 5
    second = Actor(world.app, "employee@test.test")
    payloads = [{"start_date": start, "end_date": end, "reason": "Concurrent independent three-day reservation", "expected_version": 1} for start, end in (("2026-11-02", "2026-11-04"), ("2026-11-09", "2026-11-11"))]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda pair: pair[0].post("/api/leave/requests", pair[1]), zip((world.employee, second), payloads)))
    second.client.close()
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert balance(world)["available"] == 2
    with world.db.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(LeaveRequest)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 1


def test_postgresql_concurrent_reviews_one_winner(world):
    if world.db.engine.dialect.name != "postgresql":
        pytest.skip("Requires actual PostgreSQL row locks")
    row = create_leave(world.employee)
    second = Actor(world.app, "manager@test.test")
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda pair: pair[0].post(f"/api/leave/requests/{row['id']}/{pair[1]}", {"expected_version": 1, "reason": "Simultaneous review from another browser"}), ((world.manager, "approve"), (second, "reject"))))
    second.client.close()
    assert sorted(response.status_code for response in responses) == [200, 409]
    result = world.employee.get(f"/api/leave/requests/{row['id']}").json()
    assert result["version"] == 2 and len(result["events"]) == 2
    assert balance(world)["available"] in {9, 12}
