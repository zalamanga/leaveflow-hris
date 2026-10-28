import argparse
import os
from datetime import date
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from .config import Settings
from .db import Database
from .models import AnnualGrant, CompanyHoliday, LeaveRequest, User, utcnow
from .security import hash_password
from .schemas import canonical_email
from .seed import seed_demo


def init_db(database_url):
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["database_url"] = database_url
    if database_url.startswith("sqlite") and "/.local/" in database_url:
        Path(".local").mkdir(exist_ok=True)
    command.upgrade(config, "head")


def main():
    parser = argparse.ArgumentParser(description="Manage LeaveFlow schema, accounts, annual grants and office holidays")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("init-db")
    sub.add_parser("seed-demo", help="Requires APP_DEMO_MODE and APP_DEMO_PASSWORD; synthetic once-only seed")
    user = sub.add_parser("create-user", help="Read password from APP_USER_PASSWORD")
    user.add_argument("--email", required=True)
    user.add_argument("--name", required=True)
    user.add_argument("--role", choices=("employee", "manager"), required=True)
    user.add_argument("--manager-id", type=int)
    grant = sub.add_parser("set-grant", help="Configure a yearly allowance; cannot reduce below committed + reserved days")
    grant.add_argument("--employee-id", type=int, required=True)
    grant.add_argument("--year", type=int, required=True)
    grant.add_argument("--days", type=int, required=True)
    holiday = sub.add_parser("add-holiday", help="Affects new estimates/requests only; existing snapshots remain unchanged")
    holiday.add_argument("--date", required=True)
    holiday.add_argument("--label", required=True)
    arguments = parser.parse_args()
    settings = Settings()
    if arguments.action == "init-db":
        init_db(settings.database_url)
        print("Schema is up to date")
        return
    database = Database(settings.database_url)
    try:
        with database.session_factory.begin() as db:
            if arguments.action == "seed-demo":
                if not settings.demo_mode:
                    raise ValueError("Enable APP_DEMO_MODE=true before adding training data")
                created = seed_demo(db, os.getenv("APP_DEMO_PASSWORD", ""), utcnow())
                print("Synthetic training data created" if created else "Training seed already applied; no records changed")
            elif arguments.action == "create-user":
                password = os.getenv("APP_USER_PASSWORD", "")
                if not 12 <= len(password) <= 128:
                    raise ValueError("Set APP_USER_PASSWORD to 12-128 characters")
                email, name = canonical_email(arguments.email), arguments.name.strip()
                if not 1 <= len(name) <= 100:
                    raise ValueError("Provide an email and a name of 1-100 characters")
                if db.scalar(select(User.id).where(User.email == email)):
                    raise ValueError("Email already exists; no account changed")
                manager = db.get(User, arguments.manager_id) if arguments.manager_id else None
                if arguments.role == "employee" and (not manager or manager.role != "manager" or not manager.is_active):
                    raise ValueError("An employee requires --manager-id of an active manager")
                if arguments.role == "manager" and arguments.manager_id is not None:
                    raise ValueError("Manager accounts cannot report to another manager in this focused version")
                db.add(User(email=email, name=name, role=arguments.role, manager_id=arguments.manager_id, password_hash=hash_password(password)))
                print("Account created")
            elif arguments.action == "set-grant":
                if not 2000 <= arguments.year <= 2200 or not 0 <= arguments.days <= 366:
                    raise ValueError("Year must be 2000-2200 and days 0-366")
                employee = db.scalar(select(User).where(User.id == arguments.employee_id).with_for_update())
                if not employee or employee.role != "employee":
                    raise ValueError("Employee not found")
                row = db.scalar(select(AnnualGrant).where(AnnualGrant.employee_id == employee.id, AnnualGrant.year == arguments.year).with_for_update())
                used = sum(db.scalars(select(LeaveRequest.units).where(LeaveRequest.employee_id == employee.id, LeaveRequest.year == arguments.year, LeaveRequest.status.in_(("pending", "approved")))))
                if arguments.days < used:
                    raise ValueError("Allowance cannot be less than approved + pending days")
                if row:
                    row.days = arguments.days
                    row.version += 1
                else:
                    db.add(AnnualGrant(employee_id=employee.id, year=arguments.year, days=arguments.days, version=1))
                print("Annual grant configured")
            else:
                day = date.fromisoformat(arguments.date)
                label = arguments.label.strip()
                if not 1 <= len(label) <= 160:
                    raise ValueError("Holiday label must have 1-160 characters")
                if db.get(CompanyHoliday, day):
                    raise ValueError("Holiday already exists; existing snapshots were not changed")
                db.add(CompanyHoliday(day=day, label=label))
                print("Company holiday added; existing request snapshots are unchanged")
    except ValueError as error:
        parser.exit(2, str(error) + "\n")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
