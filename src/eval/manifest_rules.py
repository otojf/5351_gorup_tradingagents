"""Interface contract for the manifest fields owned by other branches (draft).

NFR-E1's manifest has three fields the eval harness cannot fill on its own:

- ``degradations``   -- owned by A (graceful-degrade evidence). Fed from the
  DEGRADED / fallback events the run emits.
- ``risk_verdicts``  -- owned by B (risk gate). Fed from the risk-gate verdicts.
- ``traceability``   -- owned by D (evidence refs). Fed from the EvidenceRefs a
  run produced.

This module is the **interface draft only**: it fixes the field shapes and gives
the normalization boundary, but no branch wires a real producer yet. A caller
builds the normalized dicts and passes them as ``build_manifest(integrations=...)``;
anything absent stays ``None`` with a reason in ``unavailable_sources``.

Field shapes (all optional keys except where noted; lists, not single values,
so a run can record every event):

    degradations: list[dict]
        { "source": str,            # which component degraded, e.g. "fred"
          "reason": str,            # vendor error / fallback reason
          "at": str | None,         # ISO-8601 event time, if known
          "impact": str | None }    # "sentinel" | "fallback" | "skipped" | ...

    risk_verdicts: list[dict]
        { "gate": str,              # e.g. "position_size", "concentration"
          "verdict": str,           # "allow" | "flag" | "block"
          "detail": str | None }

    traceability: list[dict]
        { "claim": str,             # the claim/assertion being traced
          "evidence_ref": str }     # EvidenceRef id or path backing it

Producers hand raw records to ``normalize_integrations``; it keeps only the
known keys, drops ``None`` values, and rejects an unknown shape early so a
malformed producer fails at the seam rather than writing junk into a manifest.
"""

from __future__ import annotations

_SHAPES: dict[str, tuple[str, ...]] = {
    "degradations": ("source", "reason", "at", "impact"),
    "risk_verdicts": ("gate", "verdict", "detail"),
    "traceability": ("claim", "evidence_ref"),
}


def _normalize_records(field: str, records) -> list[dict]:
    if not isinstance(records, list):
        raise TypeError(f"{field} must be a list of dicts, got {type(records).__name__}")
    allowed = _SHAPES[field]
    normalized = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise TypeError(f"{field}[{i}] must be a dict, got {type(rec).__name__}")
        unknown = set(rec) - set(allowed)
        if unknown:
            raise ValueError(f"{field}[{i}] has unknown keys: {sorted(unknown)}")
        normalized.append({k: rec[k] for k in allowed if rec.get(k) is not None})
    return normalized


def normalize_integrations(integrations: dict | None) -> dict:
    """Validate and trim the A/B/D dicts before they enter a manifest.

    ``None`` (or an absent key) means "producer not wired"; the manifest then
    records ``None`` and a reason. A present value is normalized to the shape
    above, so unknown keys and wrong types fail here, not in the manifest file.
    """
    integrations = integrations or {}
    unknown = set(integrations) - set(_SHAPES)
    if unknown:
        raise ValueError(f"unknown integration fields: {sorted(unknown)}")
    result: dict = {}
    for field in _SHAPES:
        value = integrations.get(field)
        result[field] = None if value is None else _normalize_records(field, value)
    return result
