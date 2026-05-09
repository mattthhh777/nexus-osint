"""postgres baseline schema

Revision ID: 0001_postgres_baseline
Revises:
Create Date: 2026-05-09
"""
from __future__ import annotations

from alembic import op

revision = "0001_postgres_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS searches (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            ts timestamptz NOT NULL,
            username text NOT NULL,
            ip text,
            query text NOT NULL,
            query_type text,
            mode text,
            modules_run text[] NOT NULL DEFAULT ARRAY[]::text[],
            breach_count integer NOT NULL DEFAULT 0 CHECK (breach_count >= 0),
            stealer_count integer NOT NULL DEFAULT 0 CHECK (stealer_count >= 0),
            social_count integer NOT NULL DEFAULT 0 CHECK (social_count >= 0),
            elapsed_s double precision,
            success boolean NOT NULL DEFAULT true,
            payload jsonb NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_searches_ts ON searches (ts)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_searches_username ON searches (username)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_searches_payload_gin ON searches USING gin (payload)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS token_blacklist (
            jti text PRIMARY KEY,
            exp bigint NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_token_blacklist_exp ON token_blacklist (exp)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rate_limits (
            key text NOT NULL,
            ts double precision NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits_key ON rate_limits (key)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits_key_ts ON rate_limits (key, ts)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS quota_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            ts timestamptz NOT NULL,
            used_today integer,
            left_today integer,
            daily_limit integer
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_quota_log_ts ON quota_log (ts)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS quota_log")
    op.execute("DROP TABLE IF EXISTS rate_limits")
    op.execute("DROP TABLE IF EXISTS token_blacklist")
    op.execute("DROP TABLE IF EXISTS searches")
