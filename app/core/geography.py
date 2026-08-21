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
    re.compile(rf"\bCount(?:y|ies)\s*:\s*({_COUNTY_PATTERN})\b", re.IGNORECASE),
)
_LIST_SEPARATOR = r"(?:\s*,\s*(?:and\s+)?|\s*/\s*|\s*&\s*|\s+and\s+)"
_COUNTY_LIST = rf"({_COUNTY_PATTERN}(?:{_LIST_SEPARATOR}{_COUNTY_PATTERN})+)"
_LIST_PATTERNS = (
    re.compile(rf"\bCounties\s+of\s+{_COUNTY_LIST}\b", re.IGNORECASE),
    re.compile(rf"\b{_COUNTY_LIST}\s+Count(?:y|ies)\b", re.IGNORECASE),
    re.compile(rf"\bCounties\s*:\s*{_COUNTY_LIST}\b", re.IGNORECASE),
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
_DP_IDENTIFIER_RE = re.compile(r"\bDP\s+No\.?\s*:?\s*([A-Z0-9.-]+)", re.IGNORECASE)
_RAW_PROVENANCE_VALUES = {"SOURCE_RECORD_FIELD", "AGENCY_JURISDICTION"}


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


def _multiple_dp_identifiers(title: str) -> list[str]:
    return list(dict.fromkeys(match.group(1).rstrip(".").upper() for match in _DP_IDENTIFIER_RE.finditer(title)))


def classify_geography(record: dict[str, Any]) -> dict[str, Any]:
    """Return normalized geography without altering the record's raw county value.

    Explicit county grammar wins over source defaults. Directional labels are retained
    as regions but are never expanded into inferred counties.
    """
    raw = str(record.get("county") or "")
    title = str(record.get("title") or "")
    evidence_texts = (
        ("notice_excerpt", str(record.get("notice_excerpt") or "")),
        ("notice_text", str(record.get("notice_text") or "")),
        ("raw_text", str(record.get("raw_text") or "")),
    )

    title_counties, title_matches = _extract_explicit_counties(title)
    explicit_counties = title_counties
    explicit_field = "title"
    explicit_matches = title_matches
    if not explicit_counties:
        for field, text in evidence_texts:
            field_counties, field_matches = _extract_explicit_counties(text)
            if field_counties:
                explicit_counties = field_counties
                explicit_field = field
                explicit_matches = field_matches
                break

    raw_counties = _parse_raw_counties(raw)
    region_raw = _extract_region(raw, title)
    bistate = _is_bistate(str(record.get("source_id") or ""))
    raw_provenance = str(record.get("county_provenance") or "").upper()
    if raw_provenance not in _RAW_PROVENANCE_VALUES:
        raw_provenance = "AGENCY_JURISDICTION" if raw_counties else "NONE"
    agency_county_hint = raw if raw_counties and raw_provenance == "AGENCY_JURISDICTION" else ""
    all_notice_text = " ".join(text for _, text in evidence_texts if text)
    multiple_dp_ids = _multiple_dp_identifiers(title)

    evidence: list[str] = []
    conflict = False
    review_required = len(multiple_dp_ids) > 1
    review_reason = ""
    if review_required:
        counties = []
        confidence = "LOW"
        provenance = "NONE"
        review_reason = f"multiple DP identifiers in one record: {', '.join(multiple_dp_ids)}"
        evidence.append(f"segmentation review required; {review_reason}")
    elif explicit_counties:
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
        provenance = "NOTICE_TEXT"
    elif raw_counties and raw_provenance == "SOURCE_RECORD_FIELD":
        counties = raw_counties
        evidence.append(f'county_raw="{raw}" supplied by the official source record')
        confidence = "HIGH"
        provenance = "SOURCE_RECORD_FIELD"
    else:
        counties = []
        confidence = "LOW"
        provenance = raw_provenance
        if agency_county_hint:
            evidence.append(f'agency_county_hint="{agency_county_hint}" is not notice-level evidence')

    if review_required:
        coverage_scope = "UNRESOLVED"
    elif bistate:
        coverage_scope = "BISTATE"
        evidence.append(f'source_id="{record.get("source_id", "")}" identifies a bi-state agency')
        counties = []
        confidence = "MEDIUM" if explicit_counties else "LOW"
    elif len(counties) == 1:
        coverage_scope = "SINGLE_COUNTY"
    elif len(counties) > 1:
        coverage_scope = "MULTI_COUNTY"
    elif _STATEWIDE_RE.search(title) or _STATEWIDE_RE.search(all_notice_text):
        coverage_scope = "STATEWIDE"
        confidence = "HIGH"
        if _STATEWIDE_RE.search(title) or _STATEWIDE_RE.search(all_notice_text):
            provenance = "NOTICE_TEXT"
            evidence.append('notice text explicitly identifies statewide/systemwide scope')
    elif raw.strip().casefold() == "statewide" and raw_provenance == "SOURCE_RECORD_FIELD":
        coverage_scope = "STATEWIDE"
        confidence = "HIGH"
        provenance = "SOURCE_RECORD_FIELD"
        evidence.append('official source record identifies statewide scope')
    elif region_raw:
        coverage_scope = "REGIONAL"
        evidence.append(f'region_raw="{region_raw}" retained without county expansion (R-04)')
    else:
        coverage_scope = "UNRESOLVED"
        evidence.append("no explicit county evidence")

    if review_required:
        county_display = "Location requires review"
    elif counties:
        county_display = ", ".join(counties)
    elif coverage_scope == "STATEWIDE":
        county_display = "Statewide"
    elif coverage_scope == "BISTATE":
        county_display = "Bi-state"
    elif region_raw:
        county_display = region_raw
    else:
        county_display = "County not stated in notice"

    return {
        "counties": counties,
        "coverage_scope": coverage_scope,
        "region_raw": region_raw,
        "geography_confidence": confidence,
        "geography_provenance": provenance,
        "geography_evidence": " | ".join(dict.fromkeys(evidence)),
        "county_display": county_display,
        "geography_conflict": conflict,
        "agency_county_hint": agency_county_hint,
        "geography_review_required": review_required,
        "geography_review_reason": review_reason,
    }


def enrich_geography(record: dict[str, Any]) -> dict[str, Any]:
    record.update(classify_geography(record))
    return record

