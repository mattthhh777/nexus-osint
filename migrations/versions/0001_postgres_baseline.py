"""postgres baseline schema

Revision ID: 0001_postgres_baseline
Revises:
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_postgres_baseline"
down_revision = None
branch_labels = None
depends_on = None


metadata = sa.MetaData()

searches = sa.Table(
    "searches",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    sa.Column("username", sa.Text(), nullable=False),
    sa.Column("ip", sa.Text()),
    sa.Column("query", sa.Text(), nullable=False),
    sa.Column("query_type", sa.Text()),
    sa.Column("mode", sa.Text()),
    sa.Column(
        "modules_run",
        postgresql.ARRAY(sa.Text()),
        nullable=False,
        server_default=sa.text("ARRAY[]::text[]"),
    ),
    sa.Column(
        "breach_count",
        sa.Integer(),
        sa.CheckConstraint("breach_count >= 0", name="ck_searches_breach_count_nonnegative"),
        nullable=False,
        server_default="0",
    ),
    sa.Column(
        "stealer_count",
        sa.Integer(),
        sa.CheckConstraint("stealer_count >= 0", name="ck_searches_stealer_count_nonnegative"),
        nullable=False,
        server_default="0",
    ),
    sa.Column(
        "social_count",
        sa.Integer(),
        sa.CheckConstraint("social_count >= 0", name="ck_searches_social_count_nonnegative"),
        nullable=False,
        server_default="0",
    ),
    sa.Column("elapsed_s", sa.Float()),
    sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column(
        "payload",
        postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ),
)

token_blacklist = sa.Table(
    "token_blacklist",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("jti", sa.Text(), nullable=False, unique=True),
    sa.Column("exp", sa.BigInteger(), nullable=False),
)

rate_limits = sa.Table(
    "rate_limits",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("key", sa.Text(), nullable=False),
    sa.Column("ts", sa.Float(), nullable=False),
)

quota_log = sa.Table(
    "quota_log",
    metadata,
    sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    sa.Column("used_today", sa.Integer()),
    sa.Column("left_today", sa.Integer()),
    sa.Column("daily_limit", sa.Integer()),
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    bind = op.get_bind()
    for table in (searches, token_blacklist, rate_limits, quota_log):
        table.create(bind, checkfirst=True)

    op.create_index("idx_searches_ts", "searches", ["ts"], if_not_exists=True)
    op.create_index("idx_searches_username", "searches", ["username"], if_not_exists=True)
    op.create_index(
        "idx_searches_payload_gin",
        "searches",
        ["payload"],
        postgresql_using="gin",
        if_not_exists=True,
    )
    op.create_index("idx_token_blacklist_exp", "token_blacklist", ["exp"], if_not_exists=True)
    op.create_index("idx_rate_limits_key", "rate_limits", ["key"], if_not_exists=True)
    op.create_index("idx_rate_limits_key_ts", "rate_limits", ["key", "ts"], if_not_exists=True)
    op.create_index("idx_quota_log_ts", "quota_log", ["ts"], if_not_exists=True)


def downgrade() -> None:
    for table_name in ("quota_log", "rate_limits", "token_blacklist", "searches"):
        op.drop_table(table_name, if_exists=True)
