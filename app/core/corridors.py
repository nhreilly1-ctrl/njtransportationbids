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

# Construction titles usually identify the physical road without an
# "upcoming:" prefix: "MILLING ... SPRING VALLEY ROAD (C.R. 601)". Capture a
# short phrase ending in a roadway type, then trim project vocabulary from the
# left. Keeping the phrase short avoids turning the full solicitation title
# into a place name.
_NAMED_ROAD_RE = re.compile(
    r"\b(?P<road>(?:[A-Za-z0-9][\w.'’-]*\s+){1,4}"
    r"(?:Road|Street|Avenue|Boulevard|Lane|Drive|Highway|Causeway|Trail))\b",
    re.IGNORECASE,
)
_ROAD_BOUNDARY_WORDS = {
    "and", "at", "between", "bid", "bridge", "construction", "for", "from", "in",
    "management", "milling", "no", "of", "on", "over", "paving",
    "project", "projects", "rehabilitation", "replacement", "resurfacing",
    "route", "rt", "services", "the", "to", "various", "mounted",
}
_ROAD_GENERIC_NAMES = {"county", "federal", "state", "uez", "various"}

_ROUTE_DIRECTION_RE = re.compile(
    r"\s*,?\s*\(?\s*(?P<direction>NB|SB|EB|WB|N/B|S/B|E/B|W/B|"
    r"Northbound|Southbound|Eastbound|Westbound)\b"
    r"(?:\s*(?:&|and)\s*(?P<direction2>NB|SB|EB|WB|N/B|S/B|E/B|W/B|"
    r"Northbound|Southbound|Eastbound|Westbound)\b)?",
    re.IGNORECASE,
)
_DIRECTION_CANONICAL = {
    "NB": "NB", "N/B": "NB", "NORTHBOUND": "NB",
    "SB": "SB", "S/B": "SB", "SOUTHBOUND": "SB",
    "EB": "EB", "E/B": "EB", "EASTBOUND": "EB",
    "WB": "WB", "W/B": "WB", "WESTBOUND": "WB",
}

# A named crossing is often the most precise mappable phrase in an NJDOT
# title: "Rt 1 NB, Bridge over Raritan River". Stop before lifecycle or
# contract prose so the map query carries the physical feature, not the rest
# of the solicitation title.
_CROSSING_RE = re.compile(
    r"\b(?P<structure>Bridges?|Viaducts?|Culverts?|Tunnels?|Overpasses?|Underpasses?)\s+"
    r"(?P<relation>over|under|across|at)\s+"
    r"(?P<feature>[^,;:\n]{2,80}?)"
    r"(?=\s+(?:Pending\s+Selection|Advertised|Expected\s+posting|"
    r"Contract\s+(?:No\.?|#)|Reconstruction|Replacement)\b|[,;:]|$)",
    re.IGNORECASE,
)


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


def _extract_named_roads(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for match in _NAMED_ROAD_RE.finditer(text):
        raw_road = normalize_reference_text(match.group("road")).strip(" .")
        tokens = raw_road.split()
        boundary = max(
            (index for index, token in enumerate(tokens[:-1])
             if token.lower().strip(".,'") in _ROAD_BOUNDARY_WORDS
             and not (
                 token.lower().strip(".,'") == "bridge"
                 and index == len(tokens) - 2
             )),
            default=-1,
        )
        tokens = tokens[boundary + 1:]
        if len(tokens) >= 3 and tokens[0].isdigit():
            tokens = tokens[1:]
        name_tokens = {token.lower().strip(".,'") for token in tokens[:-1]}
        if (
            len(tokens) < 2
            or " ".join(tokens[:-1]).lower() in _ROAD_GENERIC_NAMES
            or name_tokens & _ROAD_GENERIC_NAMES
        ):
            continue
        road = " ".join(tokens)
        if road.isupper() or road.islower():
            road = " ".join(_normalize_muni_token(token) for token in tokens)
        found.append((road, match.group("road").strip()))
    return found


def _extract_directional_routes(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for match in _ROUTE_RE.finditer(text):
        system = _route_system(match)
        if system is None:
            continue
        groups = list(match.groups())
        digit_index = next(
            (i for i, value in enumerate(groups)
             if value is not None and value.isdigit()),
            None,
        )
        if digit_index is None:
            continue
        number = groups[digit_index]
        suffix = groups[digit_index + 1] or "" if digit_index + 1 < len(groups) else ""
        direction_match = _ROUTE_DIRECTION_RE.match(text, match.end())
        if not direction_match:
            continue
        direction = _DIRECTION_CANONICAL[direction_match.group("direction").upper()]
        second_direction = direction_match.group("direction2")
        if second_direction:
            direction = (
                f"{direction}/"
                f"{_DIRECTION_CANONICAL[second_direction.upper()]}"
            )
        canonical = f"{_canonical_route(system, number, suffix)} {direction}"
        surface = text[match.start():direction_match.end()].strip(" ,")
        found.append((canonical, surface))
    return found


def _extract_crossings(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for match in _CROSSING_RE.finditer(text):
        structure = match.group("structure").capitalize()
        relation = match.group("relation").lower()
        feature = normalize_reference_text(match.group("feature")).strip(" .,-")
        if not feature:
            continue
        if feature.isupper() or feature.islower():
            feature = " ".join(_normalize_muni_token(token) for token in feature.split())
        found.append(
            (f"{structure} {relation} {feature}", match.group(0).strip())
        )
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
    road_names: list[str] = []
    directional_corridors: list[str] = []
    directional_route_labels: list[str] = []
    crossing_phrases: list[str] = []
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
        for canonical, matched in _extract_named_roads(text):
            if canonical not in road_names:
                road_names.append(canonical)
                evidence.append(f'{field}:"{matched}"')
        for canonical, matched in _extract_directional_routes(text):
            if canonical not in directional_corridors:
                directional_corridors.append(canonical)
                evidence.append(f'{field}:"{matched}"')
                route_label = re.sub(
                    r"\s*,\s*", " ", normalize_reference_text(matched)
                )
                directional_route_labels.append(route_label)
        for canonical, matched in _extract_crossings(text):
            if canonical not in crossing_phrases:
                crossing_phrases.append(canonical)
                evidence.append(f'{field}:"{matched}"')

    return {
        "corridors": corridors,
        "structure_types": structures,
        "municipalities": municipalities,
        "road_names": road_names,
        "directional_corridors": directional_corridors,
        "directional_route_labels": directional_route_labels,
        "crossing_phrases": crossing_phrases,
        "location_evidence": " | ".join(dict.fromkeys(evidence)),
    }


def enrich_location(record: dict[str, Any]) -> dict[str, Any]:
    record.update(classify_location(record))
    return record


def location_display(record: dict[str, Any]) -> str:
    """Compact evidenced-location line for cards; empty when nothing extracted."""
    parts: list[str] = []
    road_names = record.get("road_names") or []
    if road_names:
        parts.append(road_names[0])
    corridors = record.get("corridors") or []
    if corridors:
        parts.append(", ".join(corridors[:3]))
    municipalities = record.get("municipalities") or []
    if municipalities:
        parts.append(municipalities[0])
    return " · ".join(parts)


def _map_county_context(record: dict[str, Any]) -> str:
    """Return a county qualifier suitable for search, not public geography.

    Explicit notice geography remains preferred. A county agency's jurisdiction
    may disambiguate a named road in a map search, but it never populates the
    public ``counties`` field or changes the page's provenance language.
    """
    if (
        record.get("geography_provenance") in ("NOTICE_TEXT", "SOURCE_RECORD_FIELD")
        and record.get("counties")
    ):
        return f"{record['counties'][0]} County"

    county_hint = str(record.get("agency_county_hint") or "").strip()
    is_county_source = (
        record.get("source_tier") == "county"
        or record.get("entity_type") == "County"
        or str(record.get("source_id") or "").startswith("county-")
    )
    if county_hint and is_county_source:
        if county_hint.lower().endswith(" county"):
            return county_hint
        return f"{county_hint} County"
    return ""


def map_query(record: dict[str, Any]) -> str:
    """Map search text built from notice tokens and labeled agency context.

    A route reference gives a corridor, not a point — the query names the
    named road, corridor, or municipality and lets the map service draw it.
    County-agency jurisdiction may disambiguate the search but is never stored
    or displayed as notice-level geography. No geocoding occurs here.
    """
    road_names = record.get("road_names") or []
    corridors = record.get("corridors") or []
    municipalities = record.get("municipalities") or []
    directional_corridors = record.get("directional_corridors") or []
    directional_route_labels = record.get("directional_route_labels") or []
    crossing_phrases = record.get("crossing_phrases") or []
    county_context = _map_county_context(record)
    # A multi-site notice does not establish a pairing between the first
    # route and first county. Keep all named places in an explicitly broad search.
    if not crossing_phrases and (len(road_names) > 1 or len(corridors) > 1):
        parts = list(road_names) + list(corridors) + list(municipalities)
        if record.get("geography_provenance") in ("NOTICE_TEXT", "SOURCE_RECORD_FIELD"):
            parts.extend(f"{county} County" for county in record.get("counties") or [])
        elif county_context:
            parts.append(county_context)
        parts.append("New Jersey")
        return ", ".join(dict.fromkeys(parts))
    if crossing_phrases:
        parts = []
        if road_names:
            parts.append(road_names[0])
        elif directional_route_labels:
            parts.append(directional_route_labels[0])
        elif directional_corridors:
            parts.append(directional_corridors[0])
        elif corridors:
            parts.append(corridors[0])
        parts.append(crossing_phrases[0])
        if county_context:
            parts.append(county_context)
        elif municipalities:
            parts.append(municipalities[0])
        parts.append("New Jersey")
        return ", ".join(parts)
    if road_names:
        parts = [road_names[0]]
        if corridors:
            parts.append(corridors[0])
        if municipalities:
            parts.append(municipalities[0])
        if county_context:
            parts.append(county_context)
        parts.append("New Jersey")
        return ", ".join(parts)
    if municipalities:
        parts = []
        if corridors:
            parts.append(corridors[0])
        parts.append(municipalities[0])
        if county_context:
            parts.append(county_context)
        parts.append("New Jersey")
        return ", ".join(parts)
    if corridors:
        parts = [corridors[0]]
        if county_context:
            parts.append(county_context)
        parts.append("New Jersey")
        return ", ".join(parts)
    return ""


def map_url(record: dict[str, Any]) -> str:
    query = map_query(record)
    if not query:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"
