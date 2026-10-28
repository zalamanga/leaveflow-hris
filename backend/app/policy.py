from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from .models import CompanyHoliday

OFFICE_ZONE = ZoneInfo("Asia/Jakarta")
POLICY = {"name": "Annual leave training policy", "office_timezone": "Asia/Jakarta", "weekend_days": [5, 6], "default_grant": 12, "carry_over": False, "legal_policy": False}


def office_today(now: datetime):
    return now.astimezone(OFFICE_ZONE).date()


def estimate(db, start: date, end: date, today: date):
    if start < today:
        raise HTTPException(422, "Tanggal mulai tidak boleh sebelum hari ini di Asia/Jakarta")
    if end < start:
        raise HTTPException(422, "Tanggal selesai harus sama atau setelah tanggal mulai")
    if start.year != end.year:
        raise HTTPException(422, "Pisahkan permintaan untuk setiap tahun kalender")
    if not 2000 <= start.year <= 2200:
        raise HTTPException(422, "Tahun harus antara 2000 dan 2200")
    holidays = {row.day: row.label for row in db.scalars(select(CompanyHoliday).where(CompanyHoliday.day >= start, CompanyHoliday.day <= end))}
    working, excluded = [], []
    day = start
    while day <= end:
        if day.weekday() >= 5:
            excluded.append({"date": day.isoformat(), "reason": "Akhir pekan"})
        elif day in holidays:
            excluded.append({"date": day.isoformat(), "reason": holidays[day]})
        else:
            working.append(day.isoformat())
        day += timedelta(days=1)
    if not working:
        raise HTTPException(422, "Rentang ini tidak memiliki hari kerja")
    return {"year": start.year, "units": len(working), "working_days": working, "excluded_days": excluded, "policy": POLICY}
