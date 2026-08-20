"""Conservative New Jersey geography normalization for procurement records."""

from __future__ import annotations

import re
from typing import Any


NJ_COUNTIES = (
    "Atlantic",
    "Bergen",
    "Burlington",
    "Camden",
    "Cape May",
    "Cumberland",
    "Essex",
    "Gloucester",
    "Hudson",
    "Hunterdon",
    "Mercer",
    "Middlesex",
    "Monmouth",
    "Morris",
    "Ocean",
    "Passaic",
    "Salem",
    "Somerset",
    "Sussex",
    "Union",
    "Warren",
)

_COUNTY_BY_KEY = {county.lower(): county for county in NJ_COUNTIES}
_COUNTY_PATTERN = "(?:" + "|".join(
    re.escape(county).replace(r"\ ", r"\s+")
    for county in sorted(NJ_COUNTIES, key=len, reverse=True)
) + ")"
_COUNTY_TOKEN_RE = re.compile(rf"\b({_COUNTY_PATTERN})\b", re.IGNORECASE)

_DIRECT_PATTERNS = (
    re.compile(rf"\bCounty\s+of\s+({_COUNTY_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\b({_COUNTY_PATTERN})\s+Count(?:y|ies)\b", re.IGNORECASE),
)
_LIST_SEPARATOR = r"(?:\s*,\s*(?:and\s+)?|\s*/\s*|\s*&\s*|\s+and\s+)"
_COUNTY_LIST = rf"({_COUNTY_PATTERN}(?:{_LIST_SEPARATOR}{_COUNTY_PATTERN})+)"
_LIST_PATTERNS = (
    re.compile(rf"\bCounties\s+of\s+{_COUNTY_LIST}\b", re.IGNORECASE),
    re.compile(rf"\b{_COUNTY_LIST}\s+Count(?:y|ies)\b", re.IGNORECASE),
)
_RAW_COUNTY_LIST_RE = re.compile(rf"^\s*{_COUNTY_LIST}\s*$", re.IGNORECASE)

_REGION_VALUES = (
    "Northern New Jersey",
    "Central & North",
    "South Region",
    "Central Region",
    "North Region",
    "North",
    "Central",
    "South",
    "Various",
)
_TITLE_REGION_PATTERNS = (
    re.compile(r"\bNorthern New Jersey\b", re.IGNORECASE),
    re.compile(r"\b(?:North|Central|South) Region\b", re.IGNORECASE),
    re.compile(r"\bCentral\s*&\s*North\b", re.IGNORECASE),
    re.compile(r"\b(?:Drainage Restoration )?Contract,?\s+(North|Central|South)\b", re.IGNORECASE),
    re.compile(r"\bPavement Preservation\s+(North|Central|South)\s+Contract\b", re.IGNORECASE),
)
_STATEWIDE_RE = re.compile(r"\b(?:statewide|state-wide|systemwide|system-wide)\b", re.IGNORECASE)
_BISTATE_SOURCE_PREFIXES = (
    "state-panynj",
    "state-drjtbc",
    "state-drpa",
)


def _canonical_county(value: str) -> str:
    return _COUNTY_BY_KEY[re.sub(r"\s+", " ", value).strip().lower()]


def _counties_in(value: str) -> list[str]:
    return sorted(
        {_canonical_county(match.group(1)) for match in _COUNTY_TOKEN_RE.finditer(value)},
        key=NJ_COUNTIES.index,
    )


def _extract_explicit_counties(text: str) -> tuple[list[str], list[str]]:
    """Extract counties only when the text explicitly labels them as counties."""
    found: set[str] = set()
    evidence: list[str] = []
    for pattern in _DIRECT_PATTERNS + _LIST_PATTERNS:
        for match in pattern.finditer(text or ""):
            matched_counties = _counties_in(match.group(0))
            if not matched_counties:
                continue
            found.update(matched_counties)
            evidence.append(match.group(0).strip())
    return sorted(found, key=NJ_COUNTIES.index), list(dict.fromkeys(evidence))


def _parse_raw_counties(raw: str) -> list[str]:
    clean = re.sub(r"\s+", " ", raw or "").strip()
    if clean.lower() in _COUNTY_BY_KEY:
        return [_canonical_county(clean)]
    match = _RAW_COUNTY_LIST_RE.fullmatch(clean)
    return _counties_in(match.group(0)) if match else []


def _extract_region(raw: str, title: str) -> str | None:
    clean_raw = re.sub(r"\s+", " ", raw or "").strip()
    for value in _REGION_VALUES:
        if clean_raw.casefold() == value.casefold():
            return clean_raw
    for pattern in _TITLE_REGION_PATTERNS:
        match = pattern.search(title or "")
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return None


def _is_bistate(source_id: str) -> bool:
    normalized = (source_id or "").lower()
    return normalized.startswith(_BISTATE_SOURCE_PREFIXES)


def classify_geography(record: dict[str, Any]) -> dict[str, Any]:
    """Return normalized geography without altering the record's raw county value.

    Explicit county grammar wins over source defaults. Directional labels are retained
    as regions but are never expanded into inferred counties.
    """
    raw = str(record.get("county") or "")
    title = str(record.get("title") or "")
    body = str(record.get("notice_text") or record.get("raw_text") or "")

    title_counties, title_matches = _extract_explicit_counties(title)
    body_counties: list[str] = []
    body_matches: list[str] = []
    if not title_counties and body:
        body_counties, body_matches = _extract_explicit_counties(body)

    explicit_counties = title_counties or body_counties
    explicit_field = "title" if title_counties else "notice"
    explicit_matches = title_matches or body_matches
    raw_counties = _parse_raw_counties(raw)
    region_raw = _extract_region(raw, title)
    bistate = _is_bistate(str(record.get("source_id") or ""))

    evidence: list[str] = []
    conflict = False
    if explicit_counties:
        counties = explicit_counties
        for match in explicit_matches:
            evidence.append(f'{explicit_field}:"{match}"')
        if raw.strip().casefold() == "statewide":
            conflict = True
        elif raw_counties and set(raw_counties) != set(explicit_counties):
            conflict = True
        if conflict:
            evidence.append(f'county_raw="{raw}" conflicts; explicit county evidence wins (R-03)')
        confidence = "MEDIUM" if conflict else "HIGH"
    elif raw_counties:
        counties = raw_counties
        evidence.append(f'county_raw="{raw}" (R-01 fallback)')
        confidence = "LOW"
    else:
        counties = []
        confidence = "LOW"

    if bistate:
        coverage_scope = "BISTATE"
        evidence.append(f'source_id="{record.get("source_id", "")}" identifies a bi-state agency')
        if not explicit_counties and not raw_counties:
            confidence = "MEDIUM"
    elif len(counties) == 1:
        coverage_scope = "SINGLE_COUNTY"
    elif len(counties) > 1:
        coverage_scope = "MULTI_COUNTY"
    elif _STATEWIDE_RE.search(title) or _STATEWIDE_RE.search(body):
        coverage_scope = "STATEWIDE"
        confidence = "HIGH"
        evidence.append('text explicitly identifies statewide/systemwide scope')
    elif region_raw:
        coverage_scope = "REGIONAL"
        evidence.append(f'region_raw="{region_raw}" retained without county expansion (R-04)')
    else:
        coverage_scope = "UNRESOLVED"
        evidence.append("no explicit county evidence")

    if counties:
        county_display = ", ".join(counties)
    elif coverage_scope == "STATEWIDE":
        county_display = "Statewide"
    elif coverage_scope == "BISTATE":
        county_display = "Bi-state"
    elif region_raw:
        county_display = region_raw
    else:
        county_display = "Location not resolved"

    return {
        "counties": counties,
        "coverage_scope": coverage_scope,
        "region_raw": region_raw,
        "geography_confidence": confidence,
        "geography_evidence": " | ".join(dict.fromkeys(evidence)),
        "county_display": county_display,
        "geography_conflict": conflict,
    }


def enrich_geography(record: dict[str, Any]) -> dict[str, Any]:
    record.update(classify_geography(record))
    return record

