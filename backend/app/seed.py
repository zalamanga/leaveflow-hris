from datetime import date, timedelta
from sqlalchemy import select
from .models import AnnualGrant, AuditEvent, CompanyHoliday, LeaveRequest, SeedMarker, User
from .policy import POLICY, OFFICE_ZONE
from .security import hash_password


def seed_demo(db, password, now):
    if not 12 <= len(password) <= 128:
        raise ValueError("Set APP_DEMO_PASSWORD to 12-128 characters")
    if db.get(SeedMarker, "leaveflow-training-v1"):
        return False
    if db.scalar(select(User.id).limit(1)):
        raise ValueError("Training seed requires an empty account database; existing users were not changed")
    encoded = hash_password(password)
    accounts = [("manager@leaveflow.test", "Training Manager Nara", "manager"), ("manager2@leaveflow.test", "Training Manager Bima", "manager"), ("employee@leaveflow.test", "Training Ayu", "employee"), ("colleague@leaveflow.test", "Training Raka", "employee"), ("second@leaveflow.test", "Training Sinta", "employee")]
    users = []
    for email, name, role in accounts:
        row = User(email=email, name=name, role=role, password_hash=encoded, is_active=True, created_at=now)
        db.add(row)
        users.append(row)
    db.flush()
    for row in users[2:4]:
        row.manager_id = users[0].id
    users[4].manager_id = users[1].id
    today = now.astimezone(OFFICE_ZONE).date()
    for employee in users[2:]:
        for year in (today.year, today.year + 1):
            db.add(AnnualGrant(employee_id=employee.id, year=year, days=12, version=1))
    future = today + timedelta(days=3)
    if future.month == 12 and future.day > 15:
        future = date(today.year + 1, 1, 5)
    while future.weekday() >= 5:
        future += timedelta(days=1)
    holiday = date(today.year + 1, 2, 3)
    db.add(CompanyHoliday(day=holiday, label="Libur kantor fiktif: kegiatan internal Training"))
    scenarios = [(users[2], future, "pending", "Training: rencana istirahat dan urusan keluarga"), (users[3], future + timedelta(days=7), "approved", "Training: kunjungan keluarga yang telah direncanakan"), (users[4], future + timedelta(days=14), "pending", "Training: urusan pribadi anggota tim lain")]
    for employee, start, status, reason in scenarios:
        while start.weekday() >= 5:
            start += timedelta(days=1)
        if start.year > today.year + 1:
            continue
        working = [start.isoformat()]
        row = LeaveRequest(employee_id=employee.id, year=start.year, start_date=start, end_date=start, working_days=working, policy_snapshot={**POLICY, "excluded_days": []}, units=1, reason=reason, status=status, reviewer_id=employee.manager_id if status == "approved" else None, version=2 if status == "approved" else 1, created_at=now - timedelta(hours=4), updated_at=now - timedelta(hours=2))
        db.add(row)
        db.flush()
        db.add(AuditEvent(request_id=row.id, actor_id=employee.id, kind="submitted", note="Contoh sintetis: permintaan satu hari", created_at=row.created_at))
        if status == "approved":
            db.add(AuditEvent(request_id=row.id, actor_id=employee.manager_id, kind="approved", note="Contoh sintetis: disetujui manajer", created_at=row.updated_at))
    db.add(SeedMarker(name="leaveflow-training-v1", completed_at=now))
    return True
