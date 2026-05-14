import sqlite3
from datetime import timezone

import pytest

from scripts.port_searches import (
    convert_row,
    parse_modules,
    parse_payload,
    parse_ts,
    port_searches,
)


def test_parse_ts_adds_utc_for_legacy_z_suffix():
    value = parse_ts("2026-01-01T00:00:00Z")
    assert value.tzinfo is not None
    assert value.utcoffset() == timezone.utc.utcoffset(value)


def test_parse_modules_converts_csv_to_array():
    assert parse_modules("breach, sherlock,,stealer") == ["breach", "sherlock", "stealer"]


def test_parse_payload_defaults_to_empty_json_object():
    assert parse_payload(None) == "{}"
    assert parse_payload("not-json") == "{}"
    assert parse_payload('{"ok": true}') == '{"ok": true}'


def _create_sqlite_searches_fixture(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """CREATE TABLE searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                username TEXT NOT NULL,
                ip TEXT,
                query TEXT NOT NULL,
                query_type TEXT,
                mode TEXT,
                modules_run TEXT,
                breach_count INTEGER,
                stealer_count INTEGER,
                social_count INTEGER,
                elapsed_s REAL,
                success INTEGER,
                payload TEXT
            )"""
        )
        conn.executemany(
            """INSERT INTO searches (
                ts, username, ip, query, query_type, mode, modules_run,
                breach_count, stealer_count, social_count, elapsed_s, success, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    "2026-01-01T00:00:00Z",
                    "admin",
                    "127.0.0.1",
                    "alice@example.com",
                    "email",
                    "full",
                    "breach,sherlock",
                    2,
                    1,
                    3,
                    1.25,
                    1,
                    '{"ok": true}',
                ),
                (
                    "2026-01-02T03:04:05+00:00",
                    "analyst",
                    None,
                    "example.com",
                    "domain",
                    "quick",
                    "",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_convert_row_defaults_legacy_values(tmp_path):
    sqlite_path = tmp_path / "legacy.db"
    _create_sqlite_searches_fixture(sqlite_path)

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM searches WHERE username = ?", ("analyst",)).fetchone()
        converted = convert_row(row)
    finally:
        conn.close()

    assert converted[6] == []
    assert converted[7] == 0
    assert converted[8] == 0
    assert converted[9] == 0
    assert converted[11] is True
    assert converted[12] == "{}"


@pytest.mark.asyncio
async def test_port_searches_runs_without_confirmation_flag(tmp_path, tmp_db, test_database_url):
    # confirm_truncate no longer required — INSERT ON CONFLICT DO NOTHING, never truncates
    sqlite_path = tmp_path / "searches.db"
    _create_sqlite_searches_fixture(sqlite_path)

    count = await port_searches(sqlite_path, test_database_url)
    assert count == 2

    rows = await tmp_db.fetch_all("SELECT username FROM searches ORDER BY ts")
    assert len(rows) == 2
    assert rows[0]["username"] == "admin"


@pytest.mark.asyncio
async def test_port_searches_is_non_destructive_on_rerun(tmp_path, tmp_db, test_database_url):
    # Two runs must not destroy existing rows. Without a unique constraint on searches,
    # duplicate rows are inserted; the important guarantee is no TRUNCATE.
    sqlite_path = tmp_path / "searches.db"
    _create_sqlite_searches_fixture(sqlite_path)

    first_count = await port_searches(sqlite_path, test_database_url, batch_size=1)
    second_count = await port_searches(sqlite_path, test_database_url, batch_size=1)

    rows = await tmp_db.fetch_all(
        "SELECT username, modules_run, breach_count, success, payload FROM searches ORDER BY ts, id"
    )

    assert first_count == 2
    assert second_count == 2
    # 4 rows expected: no TRUNCATE between runs, no unique constraint prevents re-insert
    assert len(rows) == 4
    assert rows[0]["username"] == "admin"
    assert rows[0]["modules_run"] == ["breach", "sherlock"]
    assert rows[0]["breach_count"] == 2
    assert rows[0]["success"] is True
    assert rows[0]["payload"] == '{"ok": true}'
    assert rows[1]["modules_run"] == []
    assert rows[1]["payload"] == "{}"
