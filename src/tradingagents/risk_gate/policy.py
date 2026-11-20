"""Versioned risk policy and its stable hash (FR-A1 §5.5).

The policy is code-defined constants, not runtime configuration (that is FR-A3).
``policy_hash`` is a SHA-256 over a canonical serialization of the *effective*
policy values, so changing any threshold — or the blacklist — changes the hash even
if ``version`` was not bumped. The hash is stable for equal policies.

Pure data: no network, file I/O, LLM, or LangGraph import.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from tradingagents.dataflows.symbols import normalize_symbol

DEFAULT_VERSION = "fr-a1-v1"

# Draft thresholds (FR-A1). Inclusive on the allowed side.
DEFAULT_SINGLE_NAME_CAP = 0.10
DEFAULT_SECTOR_CAP = 0.30
DEFAULT_MIN_REWARD_RISK = 1.5


def normalize_blacklist(tickers) -> frozenset[str]:
    """Canonical, order-independent blacklist set (normalized symbols)."""
    return frozenset(normalize_symbol(t) for t in tickers if isinstance(t, str) and t.strip())


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class RiskPolicy:
    """Immutable risk policy. Construct with overrides; the hash follows the values.

    ``blacklist`` accepts any iterable of tickers and is normalized on construction,
    so ``RiskPolicy(blacklist={"aapl"})`` and ``RiskPolicy(blacklist={"AAPL"})`` are
    equal and share a hash.
    """

    version: str = DEFAULT_VERSION
    single_name_cap: float = DEFAULT_SINGLE_NAME_CAP
    sector_cap: float = DEFAULT_SECTOR_CAP
    min_reward_risk: float = DEFAULT_MIN_REWARD_RISK
    blacklist: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        # Normalize the blacklist in-place on the frozen dataclass.
        object.__setattr__(self, "blacklist", normalize_blacklist(self.blacklist))

    def _hash_payload(self) -> dict:
        return {
            "version": self.version,
            "single_name_cap": float(self.single_name_cap),
            "sector_cap": float(self.sector_cap),
            "min_reward_risk": float(self.min_reward_risk),
            "blacklist": sorted(self.blacklist),
        }

    @property
    def policy_hash(self) -> str:
        """Stable SHA-256 over the effective policy values."""
        return hashlib.sha256(_canonical(self._hash_payload()).encode("utf-8")).hexdigest()

    def is_blacklisted(self, ticker: str) -> bool:
        """Whether ``ticker`` is on the blacklist under canonical normalization."""
        return normalize_symbol(ticker) in self.blacklist


DEFAULT_POLICY = RiskPolicy()
