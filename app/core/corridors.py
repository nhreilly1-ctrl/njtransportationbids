"""Corridor, structure, and municipality extraction from notice text.

Follows the same evidence discipline as ``app.core.geography``: every claim
comes from an explicit reference in notice text, the raw matched string is
preserved as evidence, and nothing here ever infers a county — a route crosses
many counties, and that inference is the same class of error the geography
work removed.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

# Em/en/figure dashes and minus signs that appear in source titles
# (e.g. "TP — 842", "I — 280"). Shared normalization for search work.
_DASH_CHARS = "‐‑‒–—―−"
_DASH_CLASS = rf"[-{_DASH_CHARS}]"


def normalize_reference_text(text: str) -> str:
    """Collapse the dash, quote, and ligature variants measured in the corpus."""
    text = re.sub(rf"\s*{_DASH_CLASS}\s*", "-", text or "")
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"\s+", " ", text).strip()


# A route number: at most three digits (never part of a longer number such as
# an RFP identifier), optionally with an attached letter suffix ("33B").
_NUM = r"(\d{1,3})(?!\d)([A-Za-z])?(?![A-Za-z0-9])"
_SEP = rf"(?:\s*{_DASH_CLASS}\s*|\s+)"
_OPT_SEP = rf"(?:\s*{_DASH_CLASS}\s*|\s*)"

# Branch order matters: the leftmost-then-first-alternative rule means
# "US Route 40" resolves as a US route before the bare "Route 40" branch,
# and "Route I — 280" resolves as an interstate.
_ROUTE_RE = re.compile(
    rf"""\b(?:
        (?:Route\s+)?(?P<interstate>I)\s*{_DASH_CLASS}\s*{_NUM}
        |(?P<interstate_word>Interstate){_SEP}{_NUM}
        |(?P<us>U\.?S\.?)(?:\s+Routes?)?{_OPT_SEP}{_NUM}
        |(?P<cr>C\.?R\.?|County\s+R(?:oute|oad)s?){_OPT_SEP}{_NUM}
        |(?P<state>Routes?|Rtes?\.?|Rts?\.?|N\.?J\.?|SR){_OPT_SEP}{_NUM}
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# After a matched route, the same designation can continue as a list:
# "Rt. 30, 40 and 47", "Route 1 & 9", "I-195/295".
_ROUTE_LIST_RE = re.compile(rf"\s*(?:,|&|/|\band\b)\s*(\d{{1,3}})(?!\d)([A-Za-z])?(?![A-Za-z0-9])")

# NJDOT notice text writes interstates and US routes with generic prefixes
# ("Route 295", "Rt 1"). New Jersey's 1953 renumbering eliminated state routes
# that duplicate an interstate or US route number, so these closed sets give a
# factual system for a bare number — a renumbering, not an inference. Applied
# only to unsuffixed numbers ("Rt 1B" and "Route 9W" keep their surface system).
_INTERSTATE_NUMBERS = {76, 78, 80, 95, 195, 278, 280, 287, 295, 676}
_US_NUMBERS = {1, 9, 22, 30, 40, 46, 130, 202, 206, 322}

_NAMED_CORRIDORS = (
    (re.compile(r"\b(?:New\s+Jersey|N\.?J\.?)\s+Turnpike\b", re.IGNORECASE), "NJ Turnpike"),
    (re.compile(r"\bGarden\s+State\s+Parkway\b", re.IGNORECASE), "Garden State Parkway"),
    (re.compile(r"\bAtlantic\s+City\s+Expressway\b", re.IGNORECASE), "Atlantic City Expressway"),
    (re.compile(r"\bPalisades\s+Interstate\s+Parkway\b", re.IGNORECASE), "Palisades Interstate Parkway"),
)

_STRUCTURE_PATTERNS = tuple(
    (re.compile(pattern, re.IGNORECASE), canonical)
    for pattern, canonical in (
        (r"\bdrawbridges?\b", "drawbridge"),
        (r"\bbridges?\b", "bridge"),
        (r"\bviaducts?\b", "viaduct"),
        (r"\boverpass(?:es)?\b", "overpass"),
        (r"\bunderpass(?:es)?\b", "underpass"),
        (r"\bculverts?\b", "culvert"),
        (r"\btunnels?\b", "tunnel"),
        (r"\binterchanges?\b", "interchange"),
        (r"\btoll\s+plazas?\b", "toll plaza"),
        (r"\banchorages?\b", "anchorage"),
    )
)

_MUNI_TYPES = ("Township", "Borough", "City", "Town", "Village")
_MUNI_TYPE_PATTERN = "|".join(_MUNI_TYPES)
_MUNI_NAME_TOKEN = r"[A-Za-z][\w.'-]*"
_MUNI_LEAD_RE = re.compile(
    rf"\b(?P<type>{_MUNI_TYPE_PATTERN})s?\s+of\s+"
    rf"(?P<name>{_MUNI_NAME_TOKEN}(?:\s+{_MUNI_NAME_TOKEN}){{0,2}})",
    re.IGNORECASE,
)
_MUNI_TRAIL_RE = re.compile(
    rf"\b(?P<name>{_MUNI_NAME_TOKEN}(?:\s+{_MUNI_NAME_TOKEN}){{0,2}})\s+"
    rf"(?P<type>{_MUNI_TYPE_PATTERN})\b(?!\s+of\b)(?!\s+Expressway\b)",
    re.IGNORECASE,
)
# Work vocabulary that ends a municipality name capture; anything at or after
# one of these words belongs to the project description, not the place name.
_MUNI_TRIM_WORDS = {
    "bridge", "bridges", "road", "roads", "roadway", "route", "routes", "rt",
    "street", "streets", "avenue", "drive", "repair", "repairs",
    "rehabilitation", "improvement", "improvements", "resurfacing", "milling",
    "paving", "drainage", "intersection", "sidewalk", "sidewalks", "signal",
    "signals", "reconstruction", "replacement", "construction", "phase",
    "project", "projects", "contract", "section", "the", "and", "for", "in",
    "at", "on", "various", "county",
}
# Places that satisfy the grammar but are not New Jersey municipalities.
_MUNI_EXCLUDED = {"new york", "new jersey", "philadelphia", "morrisville", "easton", "new castle"}


def _normalize_muni_token(token: str) -> str:
    token = token.replace("ﬁ", "fi").replace("ﬂ", "fl")
    if token.isupper() or token.islower():
        return token[:1].upper() + token[1:].lower()
    return token


def _clean_muni_name(raw_name: str, keep: str) -> str:
    """Keep the name tokens adjacent to the municipal-type word.

    A "City of X" match accretes project vocabulary on the right of the name;
    an "X Township" match accretes it on the left. Trim from the far side.
    """
    tokens = raw_name.split()
    if keep == "leading":
        kept = []
        for token in tokens:
            if token.lower().strip(".,'") in _MUNI_TRIM_WORDS:
                break
            kept.append(token)
    else:
        kept = []
        for token in reversed(tokens):
            if token.lower().strip(".,'") in _MUNI_TRIM_WORDS:
                break
            kept.insert(0, token)
    return " ".join(_normalize_muni_token(token) for token in kept)


def _extract_municipalities(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for match in _MUNI_LEAD_RE.finditer(text):
        name = _clean_muni_name(match.group("name"), keep="leading")
        if not name or name.lower() in _MUNI_EXCLUDED:
            continue
        found.append(
            (f"{match.group('type').capitalize()} of {name}",
             f"{match.group('type')} of {name}")
        )
    for match in _MUNI_TRAIL_RE.finditer(text):
        name = _clean_muni_name(match.group("name"), keep="trailing")
        if not name or name.lower() in _MUNI_EXCLUDED:
            continue
        muni_type = match.group("type").capitalize()
        found.append((f"{name} {muni_type}", f"{name} {match.group('type')}"))
    return found


def _route_system(match: re.Match) -> str | None:
    if match.group("interstate") or match.group("interstate_word"):
        token = match.group("interstate") or match.group("interstate_word")
        # A bare "I" only designates an interstate in uppercase; "Interstate"
        # is unambiguous in any case.
        if token.upper() == "I" and token != "I":
            return None
        return "I"
    if match.group("us"):
        return "US" if match.group("us").upper() == match.group("us") else None
    if match.group("cr"):
        return "CR"
    if match.group("state"):
        token = match.group("state")
        # "NJ"/"N.J." must be uppercase to be a route designation.
        if token.replace(".", "").upper() in ("NJ",) and token.upper() != token:
            return None
        return "NJ"
    return None


def _canonical_route(system: str, number: str, suffix: str) -> str:
    if system == "NJ" and not suffix:
        value = int(number)
        if value in _INTERSTATE_NUMBERS:
            system = "I"
        elif value in _US_NUMBERS:
            system = "US"
    return f"{system}-{number}{suffix.upper()}"


def _extract_routes(text: str) -> list[tuple[str, str]]:
    """Return (canonical_id, matched_text) route references in order."""
    found: list[tuple[str, str]] = []
    for match in _ROUTE_RE.finditer(text):
        system = _route_system(match)
        if system is None:
            continue
        # Each branch carries its own (number, suffix) group pair; only the
        # matched branch's groups are non-None.
        groups = list(match.groups())
        digit_index = next(
            (i for i, g in enumerate(groups) if g is not None and g.isdigit()), None
        )
        if digit_index is None:
            continue
        number = groups[digit_index]
        suffix = groups[digit_index + 1] or "" if digit_index + 1 < len(groups) else ""
        found.append((_canonical_route(system, number, suffix), match.group(0).strip()))
        # Continue a same-designation list: "Rt. 30, 40 and 47".
        position = match.end()
        while True:
            continuation = _ROUTE_LIST_RE.match(text, position)
            if not continuation:
                break
            cont_number, cont_suffix = continuation.group(1), continuation.group(2) or ""
            found.append(
                (_canonical_route(system, cont_number, cont_suffix),
                 continuation.group(0).strip(" ,&/"))
            )
            position = continuation.end()
    for pattern, canonical in _NAMED_CORRIDORS:
        for match in pattern.finditer(text):
            found.append((canonical, match.group(0).strip()))
    return found


def classify_location(record: dict[str, Any]) -> dict[str, Any]:
    """Extract corridors, structure types, and municipalities from notice text.

    Never populates counties: a corridor is a line across many counties, not
    county evidence.
    """
    evidence_texts = (
        ("title", str(record.get("title") or "")),
        ("notice_excerpt", str(record.get("notice_excerpt") or "")),
        ("notice_text", str(record.get("notice_text") or "")),
        ("raw_text", str(record.get("raw_text") or "")),
    )

    corridors: list[str] = []
    structures: list[str] = []
    municipalities: list[str] = []
    evidence: list[str] = []

    for field, text in evidence_texts:
        if not text:
            continue
        for canonical, matched in _extract_routes(text):
            if canonical not in corridors:
                corridors.append(canonical)
                evidence.append(f'{field}:"{matched}"')
        for pattern, canonical in _STRUCTURE_PATTERNS:
            match = pattern.search(text)
            if match and canonical not in structures:
                structures.append(canonical)
                evidence.append(f'{field}:"{match.group(0)}"')
        for canonical, matched in _extract_municipalities(text):
            if canonical not in municipalities:
                municipalities.append(canonical)
                evidence.append(f'{field}:"{matched}"')

    return {
        "corridors": corridors,
        "structure_types": structures,
        "municipalities": municipalities,
        "location_evidence": " | ".join(dict.fromkeys(evidence)),
    }


def enrich_location(record: dict[str, Any]) -> dict[str, Any]:
    record.update(classify_location(record))
    return record


def location_display(record: dict[str, Any]) -> str:
    """Compact evidenced-location line for cards; empty when nothing extracted."""
    parts: list[str] = []
    corridors = record.get("corridors") or []
    if corridors:
        parts.append(", ".join(corridors[:3]))
    municipalities = record.get("municipalities") or []
    if municipalities:
        parts.append(municipalities[0])
    return " · ".join(parts)


def map_query(record: dict[str, Any]) -> str:
    """Map search text built only from evidenced tokens; empty when none exist.

    A route reference gives a corridor, not a point — the query names the
    corridor or municipality and lets the map service draw it. No geocoding.
    """
    municipalities = record.get("municipalities") or []
    if municipalities:
        return f"{municipalities[0]}, New Jersey"
    corridors = record.get("corridors") or []
    if corridors:
        return f"{corridors[0]}, New Jersey"
    return ""


def map_url(record: dict[str, Any]) -> str:
    query = map_query(record)
    if not query:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"
