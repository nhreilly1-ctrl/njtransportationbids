"""Agency-keyed bid-readiness routing for a single opportunity.

Search traffic lands on individual project pages, not the homepage, so a
prospective bidder often meets this site already looking at one project for an
agency they may never have bid. This module picks the handful of already
curated references in ``app.resource_catalog`` that a bidder on *that* record
needs, in the order they would need them.

Every linked title, URL, and ``use_when`` line comes from the catalog unchanged.
Routing is intentionally conservative: it highlights agency workflow, adds
federal references only when the notice carries federal-funding evidence, and
never claims that a general resource overrides the solicitation.
"""

from __future__ import annotations

import re
from typing import Any

from app.resource_catalog import RESOURCE_SECTIONS

# Catalog entries indexed by title, with their section label attached so a
# routed item can show what stage of bidding it belongs to.
_BY_TITLE: dict[str, dict[str, Any]] = {}
for _section in RESOURCE_SECTIONS:
    for _resource in _section["resources"]:
        _BY_TITLE[_resource["title"]] = {**_resource, "stage": _section["id"], "stage_title": _section["title"]}

# Common New Jersey State and local readiness references. They are shown for
# State and local tracks, but never described as a substitute for the contract.
# Bi-state tracks instead lead with their own official procurement resources.
_NJ_STATE_BASELINE = (
    "NJ Business Registration Certificate",
    "Public Works Contractor Registration",
    "NJ Prevailing Wage Determinations",
)
_FEDERAL_AID_BY_AUDIENCE = {
    "construction": (
        "Federal Wage Determinations",
        "FHWA Buy America and BABA Guidance",
        "NJ Unified Certification Program - DBE",
    ),
    "professional_services": (
        "NJ Unified Certification Program - DBE",
    ),
}
# NJDOT states funding explicitly on both record shapes: anticipated listings
# carry "Funding: Federal." / "Funding: State.", and construction notices carry
# a "Federal Project No:". Those are evidence; the keyword list is only a
# fallback for sources that publish neither.
_FUNDING_FIELD_RE = re.compile(r"\bFunding:\s*(Federal|State)\b", re.IGNORECASE)
_FEDERAL_PROJECT_RE = re.compile(r"\bFederal\s+Project\s+No", re.IGNORECASE)
_FEDERAL_HINTS = ("federal-aid", "federal aid", "fhwa", "buy america", "davis-bacon", "davis bacon")
_NJSTART_HINTS = ("njstart", "nj start")

_CONSTRUCTION = "construction"
_PROFESSIONAL = "professional_services"


def _track(source_id: str) -> str:
    source_id = (source_id or "").lower()
    if source_id.startswith("state-njdot"):
        return "njdot"
    if source_id.startswith("state-njta"):
        return "njta"
    if source_id.startswith("state-panynj"):
        return "panynj"
    if source_id.startswith("state-njtransit"):
        return "njtransit"
    if source_id.startswith(("state-drpa", "state-drjtbc")):
        return "bistate"
    if source_id.startswith(("county-", "municipal-")):
        return "local"
    return "state_other"


# Per track: the agency label, a one-line orientation note, and ordered resource
# titles. ``priority_count`` identifies the agency actions that must lead. State
# baseline and evidenced federal references follow before secondary standards.
_TRACKS: dict[str, dict[str, Any]] = {
    "njdot": {
        "label": "NJDOT",
        "note": "NJDOT runs its own prequalification and publishes its own specifications and standard details. "
                "Prime bidders must be prequalified before bidding, and consultants need discipline prequalification "
                "and cost-basis approval before the proposal is due.",
        "priority_count": 2,
        _CONSTRUCTION: ("NJDOT Construction Prequalification", "NJDOT Bid Express and Expedite",
                        "NJDOT Standard Specifications", "NJDOT Standard Construction Details",
                        "NJDOT Baseline Document Changes"),
        _PROFESSIONAL: ("NJDOT Consultant Prequalification and Cost Basis Approval",
                        "NJDOT Professional Services Model Agreements", "NJDOT Standard Specifications",
                        "NJDOT Baseline Document Changes"),
    },
    "njta": {
        "label": "the Turnpike Authority",
        "note": "The Turnpike Authority publishes its own qualification, portal, specification, and drawing resources "
                "for Turnpike and Garden State Parkway work. Confirm the applicable process in the solicitation.",
        "priority_count": 1,
        _CONSTRUCTION: ("NJTA Construction and Maintenance Resources", "NJTA Standard Drawings",
                        "NJ Approved Surety Companies"),
        _PROFESSIONAL: ("NJTA Construction and Maintenance Resources", "NJTA Standard Drawings"),
    },
    "panynj": {
        "label": "the Port Authority",
        "note": "The Port Authority publishes its own procurement portals and vendor-profile instructions. Start with "
                "the portal named in the official notice and confirm every requirement in that solicitation.",
        "caveat": "Requirements can vary by solicitation, funding, work location, and contract type. The authority's "
                  "official bid documents control registration, labor, bonding, and submission requirements.",
        "priority_count": 1,
        _CONSTRUCTION: ("Port Authority Procurement Portals", "SBA Surety Bond Guarantee Program"),
        _PROFESSIONAL: ("Port Authority Procurement Portals",),
    },
    "bistate": {
        "label": "a bi-state authority",
        "note": "DRPA/PATCO and the DRJTBC publish agency-specific bid documents and submission instructions.",
        "caveat": "Requirements can vary by solicitation, funding, work location, and contract type. Use the official "
                  "bid documents to confirm registration, labor, bonding, and submission requirements.",
        _CONSTRUCTION: ("SBA Surety Bond Guarantee Program",),
        _PROFESSIONAL: (),
    },
    "njtransit": {
        "label": "NJ TRANSIT",
        "note": "NJ TRANSIT uses agency-specific procurement documents. Federal references appear here only when the "
                "notice states federal funding or another federal-aid signal.",
        "priority_count": 1,
        _CONSTRUCTION: ("NJ Approved Surety Companies",),
        _PROFESSIONAL: (),
    },
    "local": {
        "label": "a New Jersey county or municipality",
        "note": "County and municipal solicitations use New Jersey local-procurement forms and agency-specific bid "
                "instructions. Build the final checklist from the official solicitation.",
        "priority_count": 2,
        _CONSTRUCTION: ("NJ Local Agency Procurement Laws and Standard Bid Forms",
                        "Required Public Contract Forms Guide", "NJ Approved Surety Companies"),
        _PROFESSIONAL: ("NJ Local Agency Procurement Laws and Standard Bid Forms",
                        "Required Public Contract Forms Guide"),
    },
    "state_other": {
        "label": "a New Jersey public agency",
        "note": "Use the official solicitation to confirm vendor registration, labor, qualification, and submission "
                "requirements for this agency.",
        _CONSTRUCTION: ("Required Public Contract Forms Guide",),
        _PROFESSIONAL: ("Required Public Contract Forms Guide",),
    },
}


def _looks_federally_funded(record: dict[str, Any]) -> bool:
    """Decide federal-aid applicability from the strongest evidence present.

    An explicit "Funding: State" is an authoritative negative and outranks any
    stray use of the word federal elsewhere in the notice.
    """
    text = " ".join(
        str(record.get(field) or "") for field in ("title", "notice_excerpt", "notice_text")
    )
    stated = _FUNDING_FIELD_RE.search(text)
    if stated:
        return stated.group(1).lower() == "federal"
    if _FEDERAL_PROJECT_RE.search(text):
        return True
    lowered = text.lower()
    return any(hint in lowered for hint in _FEDERAL_HINTS)


def _uses_njstart(record: dict[str, Any]) -> bool:
    text = " ".join(
        str(record.get(field) or "")
        for field in ("platform", "source_url", "official_url", "access_type")
    ).lower()
    return any(hint in text for hint in _NJSTART_HINTS)


def _applicable_state_baseline(audience_key: str) -> list[str]:
    titles = []
    for title in _NJ_STATE_BASELINE:
        entry = _BY_TITLE.get(title)
        if not entry:
            continue
        if entry["audience"] == "Construction" and audience_key != _CONSTRUCTION:
            continue
        titles.append(title)
    return titles


def readiness_for(record: dict[str, Any], limit: int = 8) -> dict[str, Any] | None:
    """Return the bid-readiness pack for one opportunity, or None if nothing applies.

    Agency actions lead, followed by common State/local readiness items and any
    federal references supported by the record. Secondary standards fill only
    the remaining slots.
    """
    track_key = _track(str(record.get("source_id") or ""))
    track = _TRACKS.get(track_key)
    if not track:
        return None

    record_type = record.get("record_type") or record.get("notice_type")
    if record_type not in (_CONSTRUCTION, _PROFESSIONAL):
        return None
    audience_key = record_type

    agency_titles = list(track.get(audience_key) or ())
    priority_count = min(int(track.get("priority_count") or 0), len(agency_titles))
    titles = []
    if track_key == "state_other" and _uses_njstart(record):
        titles.append("NJSTART Vendor Registration")
    titles.extend(agency_titles[:priority_count])

    if "caveat" not in track:
        titles.extend(_applicable_state_baseline(audience_key))

    federal_evidence = _looks_federally_funded(record)
    if federal_evidence:
        titles.extend(_FEDERAL_AID_BY_AUDIENCE[audience_key])

    titles.extend(agency_titles[priority_count:])

    resources = []
    seen = set()
    for title in titles:
        entry = _BY_TITLE.get(title)
        if not entry or title in seen:
            continue
        seen.add(title)
        resources.append(entry)
        if len(resources) >= limit:
            break

    if not resources:
        return None
    return {
        "track": track_key,
        "label": track["label"],
        "note": track["note"],
        "caveat": track.get("caveat", ""),
        "federal_evidence": federal_evidence,
        # Not "items": Jinja resolves ``pack.items`` to the dict method first.
        "resources": resources,
    }
