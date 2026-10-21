"""Migration: User Account Security, Password Reset Lifecycle, and Role Auditing.

Revision ID: 0006_user_account_security_and_management
Revises: 0005_multi_warehouse_rbac
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_user_account_security_and_management"
down_revision = "0005_multi_warehouse_rbac"
branch_labels = None
depends_on = None


def _get_existing_columns(conn, table_name: str) -> set[str]:
    inspector = sa.inspect(conn)
    try:
        return {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return set()


def upgrade() -> None:
    conn = op.get_bind()
    user_cols = _get_existing_columns(conn, "users")

    user_new_cols = [
        ("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="SET NULL"), None),
        ("must_change_password", sa.Boolean(), None, sa.false()),
        ("password_changed_at", sa.DateTime(timezone=True), None, None),
        ("failed_login_attempts", sa.Integer(), None, sa.text("0")),
        ("locked_until", sa.DateTime(timezone=True), None, None),
        ("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), None),
    ]

    for item in user_new_cols:
        col_name = item[0]
        col_type = item[1]
        fk = item[2]
        default_val = item[3]

        if col_name not in user_cols:
            col_args = [col_type]
            if fk is not None and conn.dialect.name != "sqlite":
                col_args.append(fk)
            kwargs = {"nullable": True}
            if default_val is not None:
                kwargs["server_default"] = default_val
            op.add_column("users", sa.Column(col_name, *col_args, **kwargs))

    # Sync existing warehouse_id from user_warehouse_memberships if present
    is_active_condition = "user_warehouse_memberships.is_active = 1" if conn.dialect.name == "sqlite" else "user_warehouse_memberships.is_active IS TRUE"
    conn.execute(sa.text(f"""
        UPDATE users
        SET warehouse_id = (
            SELECT warehouse_id
            FROM user_warehouse_memberships
            WHERE user_warehouse_memberships.user_id = users.id
              AND {is_active_condition}
            LIMIT 1
        )
        WHERE warehouse_id IS NULL
    """))


def downgrade() -> None:
    pass
