"""Per-run bookkeeping for data sources skipped for missing credentials.

A vendor that is selected but has no API key is "skipped": the run records it
once, does not enter that vendor's data function again, and does not retry. The
state is a plain object created per run (never stored on a graph instance), so
two runs — even on one ``TradingAgentsGraph`` — never share skip state.

Only a safe reason code is kept (e.g. ``"fred:not_configured"``); exceptions and
credentials are never stored.

Concurrency: a run's tool workers may reach the same vendor at once. ``acquire``
makes the "already skipped / who checks first / who waits" decision under one
lock, so exactly one caller becomes the winner and enters the data function; the
rest wait on that winner's ``finish``. If the first check finds a key (not
skipped), waiters fall through to the normal call path — multiple entries are
then legitimate.
"""

from __future__ import annotations

import threading


class _Slot:
    """One in-flight first check for a vendor key."""

    __slots__ = ("event", "skipped")

    def __init__(self):
        self.event = threading.Event()
        self.skipped: bool | None = None  # None: pending, True/False: decided


class RunSkipState:
    """One run's skip bookkeeping. Safe to share across tool worker threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._coord: dict[str, _Slot] = {}      # key -> in-flight first check
        self._skipped: set[str] = set()         # keys confirmed missing credentials

    def acquire(self, key: str) -> tuple[str, _Slot | None]:
        """Decide this caller's role for ``key`` atomically.

        Returns ("skipped", None) if already known missing credentials,
        ("winner", slot) if this caller must run the config check, or
        ("waiter", slot) if another caller is checking and this one waits.
        """
        with self._lock:
            if key in self._skipped:
                return ("skipped", None)
            slot = self._coord.get(key)
            if slot is None:
                slot = _Slot()
                self._coord[key] = slot
                return ("winner", slot)
            return ("waiter", slot)

    def finish(self, key: str, slot: _Slot, skipped: bool) -> bool:
        """Publish the winner's outcome and wake waiters. Call from a finally.

        Returns True only if this is the FIRST time ``key`` is recorded skipped,
        so the caller can emit exactly one skip notice per run.
        """
        newly_skipped = False
        with self._lock:
            slot.skipped = skipped
            if skipped and key not in self._skipped:
                self._skipped.add(key)
                newly_skipped = True
            if self._coord.get(key) is slot:
                del self._coord[key]
        slot.event.set()
        return newly_skipped

    def wait(self, slot: _Slot, timeout: float = 30.0) -> bool | None:
        """Wait for the winner to finish; return True/False, or None on timeout."""
        if not slot.event.wait(timeout):
            return None
        return bool(slot.skipped)
