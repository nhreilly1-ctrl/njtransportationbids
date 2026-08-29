"""Rank sibling opportunities by evidenced overlap with one record.

The public detail page previously offered three same-agency, same-type records
picked by deadline. With 70 live NJDOT records that is close to an arbitrary
draw. A bidder reading a US-1 bridge notice is far more likely to want the
other US-1 work, or the other bridge work in the same county, than the next
NJDOT professional-services item to close.

Scoring uses only evidenced fields extracted from notice text. Exact crossings
and named roads outrank broader corridor, county, and structure overlap. Agency
and work type only break ties; they never make unrelated work look related.
"""

from __future__ import annotations

from typing import Any, Iterable

# Decimal place values encode a strict hierarchy. The sum of every lower tier
# cannot outrank a single match in the tier above it.
_CROSSING_POINTS = 1_000_000
_ROAD_POINTS = 100_000
_CORRIDOR_POINTS = 10_000
_COUNTY_POINTS = 1_000
_STRUCTURE_POINTS = 100
_AGENCY_POINTS = 10
_TYPE_POINTS = 1

_LIVE_STATUSES = ("open", "upcoming")


def _match_key(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _shared(record: dict[str, Any], other: dict[str, Any], field: str) -> list[str]:
    mine = [value for value in (record.get(field) or []) if _match_key(value)]
    theirs = {_match_key(value) for value in (other.get(field) or []) if _match_key(value)}
    return [value for value in mine if _match_key(value) in theirs]


def _relation_label(crossings: list[str], roads: list[str], corridors: list[str],
                    counties: list[str], structures: list[str], same_agency: bool,
                    other: dict[str, Any]) -> str:
    """Say why this record is being shown, most specific reason first."""
    if crossings:
        return f"Same crossing: {crossings[0]}"
    if roads:
        return f"Also on {roads[0]}"
    if corridors:
        return f"Also on {corridors[0]}"
    if counties:
        plural = "counties" if len(counties) > 1 else "County"
        return f"Also in {', '.join(counties[:2])} {plural}"
    if structures:
        return f"Also {structures[0]} work"
    if same_agency:
        return f"Also from {other.get('source_name') or 'this agency'}"
    return ""


def score_related(record: dict[str, Any], other: dict[str, Any]) -> tuple[int, str]:
    """Return an overlap score and a human reason for showing ``other``."""
    crossings = _shared(record, other, "crossing_phrases")
    roads = _shared(record, other, "road_names")
    corridors = _shared(record, other, "corridors")
    counties = _shared(record, other, "counties")
    structures = _shared(record, other, "structure_types")
    same_agency = bool(record.get("source_id")) and record.get("source_id") == other.get("source_id")
    same_type = bool(record.get("record_type")) and record.get("record_type") == other.get("record_type")

    # Work type is too broad to establish a relationship by itself. Agency is
    # retained as an honest fallback for records with sparse location evidence.
    if not any((crossings, roads, corridors, counties, structures, same_agency)):
        return 0, ""

    score = _CROSSING_POINTS if crossings else 0
    score += _ROAD_POINTS if roads else 0
    score += _CORRIDOR_POINTS if corridors else 0
    score += _COUNTY_POINTS if counties else 0
    score += _STRUCTURE_POINTS if structures else 0
    score += _AGENCY_POINTS if same_agency else 0
    score += _TYPE_POINTS if same_type else 0
    reason = _relation_label(crossings, roads, corridors, counties, structures, same_agency, other)
    return score, reason


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
        # Sooner deadlines break ties; the ID provides deterministic ordering
        # when two equally related anticipated records have no exact deadline.
        scored.append((
            -score,
            str(other.get("due_date_parsed") or "9999"),
            str(other.get("id") or ""),
            reason,
            other,
        ))
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    return [{**other, "relation_reason": reason} for _, _, _, reason, other in scored[:limit]]
