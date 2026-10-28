"""Initial LeaveFlow schema."""
from alembic import op
import sqlalchemy as sa
revision = "001_leaveflow"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(254), nullable=False, unique=True), sa.Column("name", sa.String(100), nullable=False), sa.Column("role", sa.String(20), nullable=False), sa.Column("manager_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("password_hash", sa.String(512), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("role IN ('employee','manager')", name="ck_user_role"), sa.CheckConstraint("manager_id IS NULL OR manager_id <> id", name="ck_user_no_self_manager"))
    op.create_index("ix_users_manager_id", "users", ["manager_id"])
    op.create_table("sessions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("token_hash", sa.String(64), unique=True, nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("csrf_token", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_table("annual_grants", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("employee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("days", sa.Integer(), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.UniqueConstraint("employee_id", "year", name="uq_grant_employee_year"), sa.CheckConstraint("days >= 0 AND days <= 366", name="ck_grant_days"), sa.CheckConstraint("year >= 2000 AND year <= 2200", name="ck_grant_year"), sa.CheckConstraint("version >= 1", name="ck_grant_version"))
    op.create_index("ix_annual_grants_employee_id", "annual_grants", ["employee_id"])
    op.create_table("company_holidays", sa.Column("day", sa.Date(), primary_key=True), sa.Column("label", sa.String(160), nullable=False))
    op.create_table("leave_requests", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("employee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False), sa.Column("working_days", sa.JSON(), nullable=False), sa.Column("policy_snapshot", sa.JSON(), nullable=False), sa.Column("units", sa.Integer(), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("review_reason", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.CheckConstraint("status IN ('pending','approved','rejected','withdrawn','cancelled')", name="ck_leave_status"), sa.CheckConstraint("units > 0 AND units <= 366", name="ck_leave_units"), sa.CheckConstraint("end_date >= start_date", name="ck_leave_dates"), sa.CheckConstraint("version >= 1", name="ck_leave_version"))
    op.create_index("ix_leave_requests_employee_id", "leave_requests", ["employee_id"])
    op.create_index("ix_leave_employee_status_dates", "leave_requests", ["employee_id", "status", "start_date", "end_date"])
    op.create_table("audit_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("request_id", sa.Integer(), sa.ForeignKey("leave_requests.id", ondelete="CASCADE"), nullable=False), sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("kind", sa.String(40), nullable=False), sa.Column("note", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_table("rate_limit_buckets", sa.Column("key", sa.String(64), primary_key=True), sa.Column("window_start", sa.DateTime(timezone=True), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False))
    op.create_table("seed_markers", sa.Column("name", sa.String(100), primary_key=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    for name in ("seed_markers", "rate_limit_buckets", "audit_events", "leave_requests", "company_holidays", "annual_grants", "sessions", "users"):
        op.drop_table(name)
