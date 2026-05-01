"""Unit tests for api/budget.py -- Phase 16 Thordata budget tracker."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import api.budget as budget
from api.config import THORDATA_DAILY_BUDGET_BYTES


@pytest.fixture(autouse=True)
def _reset_budget_state(monkeypatch):
    """Each test starts with fresh module state."""
    monkeypatch.setattr(budget, "_bytes_today", 0)
    monkeypatch.setattr(budget, "_requests_today", 0)
    monkeypatch.setattr(budget, "_current_day", datetime.now(timezone.utc).date())
    monkeypatch.setattr(budget, "_proxy_active", False)


def test_record_usage_increments_counters():
    budget.record_usage(1000)
    assert budget._bytes_today == 1000
    assert budget._requests_today == 1


def test_hard_limit_exceeded_when_over_budget(monkeypatch):
    monkeypatch.setattr(budget, "_bytes_today", THORDATA_DAILY_BUDGET_BYTES + 1)
    assert budget.is_hard_limit_exceeded() is True


def test_hard_limit_not_exceeded_under_budget():
    budget.record_usage(1000)
    assert budget.is_hard_limit_exceeded() is False


def test_utc_midnight_resets_counters(monkeypatch):
    budget.record_usage(5_000_000)
    # Simulate yesterday by patching _current_day to one day before today
    yesterday = budget._current_day - timedelta(days=1)
    monkeypatch.setattr(budget, "_current_day", yesterday)
    # Next call triggers _maybe_reset()
    budget.record_usage(100)
    assert budget._bytes_today == 100  # only the post-reset write
    assert budget._requests_today == 1


def test_get_metrics_keys_exact():
    m = budget.get_metrics()
    assert set(m.keys()) == {"bytes_today_mb", "requests_today", "budget_remaining_pct", "proxy_active"}


def test_get_metrics_remaining_pct_clamped_at_zero(monkeypatch):
    monkeypatch.setattr(budget, "_bytes_today", THORDATA_DAILY_BUDGET_BYTES * 2)
    m = budget.get_metrics()
    assert m["budget_remaining_pct"] == 0.0
