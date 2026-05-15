"""enable pg_stat_statements

Revision ID: 0002_enable_pg_stat_statements
Revises: 0001_postgres_baseline
Create Date: 2026-05-11
"""

from alembic import op


revision = "0002_enable_pg_stat_statements"
down_revision = "0001_postgres_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_stat_statements")
