from __future__ import annotations

from datetime import timezone

from scripts.port_searches import parse_modules, parse_payload, parse_ts


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
