"""Backward-compatible alias for the username check runner.

Phase A keeps old imports and monkeypatch behavior valid:
`from modules.sherlock_wrapper import search_username` still resolves to the
same module state used by the runner.
"""
from __future__ import annotations

import sys

from modules.username_check import runner as _runner

sys.modules[__name__] = _runner
