"""FR-C2: credential skips shared by a run's tools, isolated from other runs.

Only absence of configuration is remembered. Network failures and rate limits
retain the router's existing behavior. No credential values enter this state.
"""

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class VendorRunState:
    run_id: str = field(default_factory=lambda: uuid4().hex)
    _skipped: dict[str, str] = field(default_factory=dict, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    @property
    def vendor_skip_count(self) -> int:
        """Number of distinct suppliers skipped, not tool calls or HTTP retries."""
        with self._lock:
            return len(self._skipped)

    def _record_skip(self, vendor: str, method: str, reason: str) -> str:
        # Called under the lock: concurrent tools share one transition/event.
        if vendor not in self._skipped:
            self._skipped[vendor] = reason
            logger.warning(
                "vendor_skipped vendor=%s reason=%s run_id=%s",
                vendor, reason, self.run_id,
                extra={"event": "vendor_skipped", "vendor": vendor, "method": method,
                       "reason": reason, "run_id": self.run_id, "vendor_skip_count": 1},
            )
        return self._skipped[vendor]

    def skip_reason(self, vendor: str, method: str) -> str | None:
        with self._lock:
            if vendor in self._skipped:
                return self._skipped[vendor]
            # FR-C2's initial scope is FRED. Keyless suppliers are never skipped
            # just because they have no key. No remote authentication probe.
            if vendor == "fred" and not (os.getenv("FRED_API_KEY") or "").strip():
                return self._record_skip(vendor, method, "missing_credentials")
            return None

    def record_not_configured(self, vendor: str, method: str) -> str:
        with self._lock:
            return self._record_skip(vendor, method, "not_configured")


_current: ContextVar[VendorRunState | None] = ContextVar("vendor_run_state", default=None)


def current_vendor_run() -> VendorRunState | None:
    return _current.get()


def ensure_vendor_run_state() -> VendorRunState:
    """Bind in an isolated stream context, reusing an enclosing analysis if any."""
    state = _current.get()
    if state is None:
        state = VendorRunState()
        _current.set(state)
    return state


@contextmanager
def vendor_run_scope():
    """A new analysis; copied worker contexts share this object's locked state."""
    state = VendorRunState()
    token = _current.set(state)
    try:
        yield state
    finally:
        _current.reset(token)
