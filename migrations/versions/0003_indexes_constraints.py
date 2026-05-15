"""Add unique constraint on rate_limits and indexes on searches

Revision ID: 0003_indexes_constraints
Revises: 0002_enable_pg_stat_statements
Create Date: 2026-05-13
"""

from alembic import op


revision = "0003_indexes_constraints"
down_revision = "0002_enable_pg_stat_statements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # H10: prevent duplicate rate-limit rows for the same (key, ts) bucket
    op.execute(
        "ALTER TABLE rate_limits ADD CONSTRAINT uq_rate_limits_key_ts UNIQUE (key, ts)"
    )

    # H11: speed up per-user search history queries (user feed, admin audit)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_searches_username_ts "
        "ON searches (username, ts DESC)"
    )

    # H11: speed up keyset pagination on the admin logs endpoint
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_searches_ts_id_desc "
        "ON searches (ts DESC, id DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_searches_ts_id_desc")
    op.execute("DROP INDEX IF EXISTS idx_searches_username_ts")
    op.execute(
        "ALTER TABLE rate_limits DROP CONSTRAINT IF EXISTS uq_rate_limits_key_ts"
    )
