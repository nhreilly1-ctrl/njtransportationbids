"""Rank sibling opportunities by evidenced overlap with one record.

The public detail page previously offered three same-agency, same-type records
picked by deadline. With 70 live NJDOT records that is close to an arbitrary
draw. A bidder reading a US-1 bridge notice is far more likely to want the
other US-1 work, or the other bridge work in the same county, than the next
NJDOT professional-services item to close.

Scoring uses only evidenced fields — the corridors, counties, and structure
types extracted from notice text — so a stated relationship is always one the
notices themselves support.
"""

from __future__ import annotations

from typing import Any, Iterable

_CORRIDOR_POINTS = 5
_COUNTY_POINTS = 3
_STRUCTURE_POINTS = 2
_AGENCY_POINTS = 1
_TYPE_POINTS = 1
_MAX_CORRIDOR_POINTS = 10
_MAX_COUNTY_POINTS = 6

_LIVE_STATUSES = ("open", "upcoming")


def _shared(record: dict[str, Any], other: dict[str, Any], field: str) -> list[str]:
    mine = [value for value in (record.get(field) or []) if value]
    theirs = {value for value in (other.get(field) or []) if value}
    return [value for value in mine if value in theirs]


def _relation_label(corridors: list[str], counties: list[str], structures: list[str],
                    same_agency: bool, other: dict[str, Any]) -> str:
    """Say why this record is being shown, most specific reason first."""
    if corridors:
        return f"Also on {corridors[0]}"
    if counties:
        plural = "counties" if len(counties) > 1 else "County"
        return f"Also in {', '.join(counties[:2])} {plural}"
    if structures:
        return f"Also {structures[0]} work"
    if same_agency:
        return f"Also from {other.get('source_name') or 'this agency'}"
    return "Similar work type"


def score_related(record: dict[str, Any], other: dict[str, Any]) -> tuple[int, str]:
    """Return an overlap score and a human reason for showing ``other``."""
    corridors = _shared(record, other, "corridors")
    counties = _shared(record, other, "counties")
    structures = _shared(record, other, "structure_types")
    same_agency = bool(record.get("source_id")) and record.get("source_id") == other.get("source_id")
    same_type = bool(record.get("record_type")) and record.get("record_type") == other.get("record_type")

    score = min(len(corridors) * _CORRIDOR_POINTS, _MAX_CORRIDOR_POINTS)
    score += min(len(counties) * _COUNTY_POINTS, _MAX_COUNTY_POINTS)
    score += _STRUCTURE_POINTS if structures else 0
    score += _AGENCY_POINTS if same_agency else 0
    score += _TYPE_POINTS if same_type else 0
    return score, _relation_label(corridors, counties, structures, same_agency, other)


def rank_related(record: dict[str, Any], pool: Iterable[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    """Return up to ``limit`` live siblings, most related first, each labelled."""
    scored = []
    for other in pool:
        if other.get("id") == record.get("id"):
            continue
        if other.get("status") not in _LIVE_STATUSES:
            continue
        score, reason = score_related(record, other)
        if score <= 0:
            continue
        # Sooner deadlines break ties so equally related work stays actionable.
        scored.append((-score, str(other.get("due_date_parsed") or "9999"), reason, other))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [{**other, "relation_reason": reason} for _, _, reason, other in scored[:limit]]
