"""real-time OSINT job store - hash-only payload + TTL 7d (G1)

Revision ID: 0004_real_time_osint_jobs
Revises: 0003_indexes_constraints
Create Date: 2026-05-19

owner_key_hash is a privacy-preserving owner identifier aligned with current
JSON auth. It is intentionally not a FK until DB-backed users exist.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0004_real_time_osint_jobs"
down_revision = "0003_indexes_constraints"
branch_labels = None
depends_on = None


OWNER_KEY_HASH_COMMENT = (
    "owner_key_hash is a privacy-preserving owner identifier aligned with "
    "current JSON auth. It is intentionally not a FK until DB-backed users exist."
)


def upgrade() -> None:
    op.create_table(
        "search_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("owner_key_hash", sa.Text(), nullable=True),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_hash", sa.Text(), nullable=False),
        sa.Column("target_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("overall_status", sa.Text(), nullable=True),
        sa.Column("overall_confidence", sa.Integer(), nullable=True),
        sa.Column("connectors_planned", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("connectors_run", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column(
            "expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("(NOW() + INTERVAL '7 days')"),
        ),
        sa.CheckConstraint(
            "owner_key_hash IS NULL OR owner_key_hash ~ '^[a-f0-9]{64}$'",
            name="ck_search_jobs_owner_key_hash_hmac_sha256_hex",
        ),
        sa.CheckConstraint(
            "target_type IN ('username', 'email', 'phone')",
            name="ck_search_jobs_target_type",
        ),
        sa.CheckConstraint(
            "target_hash ~ '^[a-f0-9]{12}$'",
            name="ck_search_jobs_target_hash_sha256_12",
        ),
        sa.CheckConstraint(
            "target_encrypted IS NULL",
            name="ck_search_jobs_g1_target_encrypted_null",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')",
            name="ck_search_jobs_status",
        ),
        sa.CheckConstraint(
            "overall_status IS NULL OR overall_status IN "
            "('pending', 'running', 'found', 'likely', 'not_found', "
            "'uncertain', 'blocked', 'error')",
            name="ck_search_jobs_overall_status_8_state",
        ),
        sa.CheckConstraint(
            "overall_confidence IS NULL OR "
            "(overall_confidence >= 0 AND overall_confidence <= 100)",
            name="ck_search_jobs_overall_confidence_range",
        ),
        sa.CheckConstraint(
            "elapsed_ms IS NULL OR elapsed_ms >= 0",
            name="ck_search_jobs_elapsed_ms_nonnegative",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_search_jobs_finished_after_started",
        ),
        sa.CheckConstraint(
            "expires_at >= created_at + INTERVAL '7 days' - INTERVAL '1 second'",
            name="ck_search_jobs_retention_min_7d",
        ),
    )
    op.execute(f"COMMENT ON COLUMN search_jobs.owner_key_hash IS {OWNER_KEY_HASH_COMMENT!r}")
    op.execute(
        "COMMENT ON COLUMN search_jobs.expires_at IS "
        "'G1 retention boundary: search job events expire after 7 days; "
        "events cascade when the job is purged.'"
    )
    op.execute(
        "COMMENT ON COLUMN search_jobs.target_encrypted IS "
        "'G1 hash-only mode: must remain NULL in R1; no raw target encryption or key management.'"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_search_jobs_owner_key_hash_created_at "
        "ON search_jobs (owner_key_hash, created_at DESC)"
    )
    op.create_index(
        "ix_search_jobs_expires_at",
        "search_jobs",
        ["expires_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_search_jobs_target_hash",
        "search_jobs",
        ["target_hash"],
        if_not_exists=True,
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_search_jobs_status_created_at "
        "ON search_jobs (status, created_at DESC)"
    )

    op.create_table(
        "search_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "emitted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("seq >= 1", name="ck_search_events_seq_positive"),
        sa.CheckConstraint("event_type <> ''", name="ck_search_events_event_type_nonempty"),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ck_search_events_payload_object",
        ),
        sa.CheckConstraint(
            "payload ? 'target_hash' AND (payload->>'target_hash') ~ '^[a-f0-9]{12}$'",
            name="ck_search_events_payload_target_hash",
        ),
        sa.CheckConstraint(
            "NOT ("
            "jsonb_path_exists(payload, '$.**.target') OR "
            "jsonb_path_exists(payload, '$.**.target_value') OR "
            "jsonb_path_exists(payload, '$.**.raw_target') OR "
            "jsonb_path_exists(payload, '$.**.query') OR "
            "jsonb_path_exists(payload, '$.**.raw') OR "
            "jsonb_path_exists(payload, '$.**.raw_url') OR "
            "jsonb_path_exists(payload, '$.**.url') OR "
            "jsonb_path_exists(payload, '$.**.profile_url') OR "
            "jsonb_path_exists(payload, '$.**.request_url') OR "
            "jsonb_path_exists(payload, '$.**.raw_response') OR "
            "jsonb_path_exists(payload, '$.**.headers') OR "
            "jsonb_path_exists(payload, '$.**.body') OR "
            "jsonb_path_exists(payload, '$.**.request_headers') OR "
            "jsonb_path_exists(payload, '$.**.response_headers') OR "
            "jsonb_path_exists(payload, '$.**.request_body') OR "
            "jsonb_path_exists(payload, '$.**.response_body') OR "
            "jsonb_path_exists(payload, '$.**.cookies') OR "
            "jsonb_path_exists(payload, '$.**.cookie') OR "
            "jsonb_path_exists(payload, '$.**.authorization') OR "
            "jsonb_path_exists(payload, '$.**.auth') OR "
            "jsonb_path_exists(payload, '$.**.bearer') OR "
            "jsonb_path_exists(payload, '$.**.token') OR "
            "jsonb_path_exists(payload, '$.**.secret') OR "
            "jsonb_path_exists(payload, '$.**.api_key') OR "
            "jsonb_path_exists(payload, '$.**.password') OR "
            "jsonb_path_exists(payload, '$.**.credential') OR "
            "jsonb_path_exists(payload, '$.**.credentials') OR "
            "jsonb_path_exists(payload, '$.**.session') OR "
            "jsonb_path_exists(payload, '$.**.set_cookie') OR "
            "jsonb_path_exists(payload, '$.**.email') OR "
            "jsonb_path_exists(payload, '$.**.account_email') OR "
            "jsonb_path_exists(payload, '$.**.phone') OR "
            "jsonb_path_exists(payload, '$.**.phone_number') OR "
            "jsonb_path_exists(payload, '$.**.cpf') OR "
            "jsonb_path_exists(payload, '$.**.document') OR "
            "jsonb_path_exists(payload, '$.**.sensitive')"
            ")",
            name="ck_search_events_payload_no_sensitive_keys",
        ),
        sa.CheckConstraint(
            "payload::text !~* '[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}' "
            "AND payload::text !~ '\\m[0-9]{3}\\.?[0-9]{3}\\.?[0-9]{3}-?[0-9]{2}\\M' "
            "AND payload::text !~ '(\\+?[0-9]{1,3}[ .-]?)?\\(?[0-9]{2,3}\\)?[ .-]?[0-9]{4,5}[ .-][0-9]{4}' "
            "AND payload::text !~* 'https?://'",
            name="ck_search_events_payload_no_raw_pii",
        ),
        sa.UniqueConstraint("job_id", "seq", name="uq_search_events_job_seq"),
    )
    op.execute(
        "COMMENT ON COLUMN search_events.payload IS "
        "'G1 hash-only payload: target_hash plus sanitized metadata only; "
        "no target_value, raw query, headers, body, credentials, email, phone, "
        "CPF, raw URL, or raw response.'"
    )

    op.create_index(
        "ix_search_events_job_id_seq",
        "search_events",
        ["job_id", "seq"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_search_events_job_id_seq", table_name="search_events")
    op.drop_table("search_events")
    op.drop_index("ix_search_jobs_status_created_at", table_name="search_jobs")
    op.drop_index("ix_search_jobs_target_hash", table_name="search_jobs")
    op.drop_index("ix_search_jobs_expires_at", table_name="search_jobs")
    op.drop_index("ix_search_jobs_owner_key_hash_created_at", table_name="search_jobs")
    op.drop_table("search_jobs")
