"""Agency-keyed bid-readiness routing for a single opportunity.

Search traffic lands on individual project pages, not the homepage, so a
prospective bidder often meets this site already looking at one project for an
agency they may never have bid. This module picks the handful of already
curated references in ``app.resource_catalog`` that a bidder on *that* record
needs, in the order they would need them.

It writes no new guidance: every title, URL, and ``use_when`` line comes from
the catalog unchanged. The only judgement here is which entries apply to which
record, and — for bi-state authorities — which New Jersey State requirements
must be kept off the page because they do not apply.
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

# New Jersey State and local contracting requirements. They are the right
# default for State agency and local public work, and are deliberately withheld
# from bi-state authority records, which run under their own compact rules.
_NJ_STATE_BASELINE = (
    "NJ Business Registration Certificate",
    "Public Works Contractor Registration",
    "NJ Prevailing Wage Determinations",
)
_FEDERAL_AID = (
    "Federal Wage Determinations",
    "FHWA Buy America and BABA Guidance",
    "NJ Unified Certification Program - DBE",
)
# NJDOT states funding explicitly on both record shapes: anticipated listings
# carry "Funding: Federal." / "Funding: State.", and construction notices carry
# a "Federal Project No:". Those are evidence; the keyword list is only a
# fallback for sources that publish neither.
_FUNDING_FIELD_RE = re.compile(r"\bFunding:\s*(Federal|State)\b", re.IGNORECASE)
_FEDERAL_PROJECT_RE = re.compile(r"\bFederal\s+Project\s+No", re.IGNORECASE)
_FEDERAL_HINTS = ("federal-aid", "federal aid", "fhwa", "buy america", "davis-bacon", "davis bacon")

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


# Per track: the agency label, a one-line orientation note, and the ordered
# titles to route for construction and for professional-services records.
_TRACKS: dict[str, dict[str, Any]] = {
    "njdot": {
        "label": "NJDOT",
        "note": "NJDOT runs its own prequalification and publishes its own specifications and standard details. "
                "Prime bidders must be prequalified before bidding, and consultants need discipline prequalification "
                "and cost-basis approval before the proposal is due.",
        _CONSTRUCTION: ("NJDOT Construction Prequalification", "NJDOT Standard Specifications",
                        "NJDOT Standard Construction Details", "NJDOT Baseline Document Changes",
                        "NJDOT Bid Express and Expedite"),
        _PROFESSIONAL: ("NJDOT Consultant Prequalification and Cost Basis Approval",
                        "NJDOT Professional Services Model Agreements", "NJDOT Standard Specifications",
                        "NJDOT Baseline Document Changes"),
    },
    "njta": {
        "label": "the Turnpike Authority",
        "note": "The Turnpike Authority prequalifies contractors separately from NJDOT and issues its own standard "
                "drawings and specifications for the Turnpike and Garden State Parkway. NJDOT approval does not carry over.",
        _CONSTRUCTION: ("NJTA Construction and Maintenance Resources", "NJTA Standard Drawings",
                        "NJ Approved Surety Companies"),
        _PROFESSIONAL: ("NJTA Construction and Maintenance Resources", "NJTA Standard Drawings"),
    },
    "panynj": {
        "label": "the Port Authority",
        "note": "The Port Authority is a bi-state agency with its own procurement portals and vendor profiles, "
                "separate from any New Jersey State registration.",
        "caveat": "As a bi-state authority, the Port Authority sets its own contracting rules. New Jersey State "
                  "requirements such as the Business Registration Certificate, Public Works Contractor Registration, "
                  "and NJ prevailing wage do not apply the same way — follow the authority's own solicitation terms.",
        _CONSTRUCTION: ("Port Authority Procurement Portals", "NJ Approved Surety Companies",
                        "SBA Surety Bond Guarantee Program"),
        _PROFESSIONAL: ("Port Authority Procurement Portals",),
    },
    "bistate": {
        "label": "a bi-state authority",
        "note": "DRPA/PATCO and the DRJTBC are bi-state compact agencies. They publish their own bid documents and "
                "run procurement under their own rules rather than New Jersey's.",
        "caveat": "As a bi-state authority, this agency sets its own contracting rules. New Jersey State requirements "
                  "such as the Business Registration Certificate, Public Works Contractor Registration, and NJ "
                  "prevailing wage do not apply the same way — follow the authority's own solicitation terms.",
        _CONSTRUCTION: ("NJ Approved Surety Companies", "SBA Surety Bond Guarantee Program"),
        _PROFESSIONAL: (),
    },
    "njtransit": {
        "label": "NJ TRANSIT",
        "note": "NJ TRANSIT procurements are frequently federally funded, which brings federal wage determinations, "
                "Buy America content rules, and DBE participation goals into the bid.",
        _CONSTRUCTION: ("NJ Unified Certification Program - DBE", "NJ Approved Surety Companies"),
        _PROFESSIONAL: ("NJ Unified Certification Program - DBE",),
    },
    "local": {
        "label": "a New Jersey county or municipality",
        "note": "Local public work runs under the Local Public Contracts Law, which sets the bid forms, the "
                "advertisement rules, and the mandatory submission documents.",
        _CONSTRUCTION: ("NJ Local Agency Procurement Laws and Standard Bid Forms",
                        "Required Public Contract Forms Guide", "NJ Approved Surety Companies"),
        _PROFESSIONAL: ("NJ Local Agency Procurement Laws and Standard Bid Forms",
                        "Required Public Contract Forms Guide"),
    },
    "state_other": {
        "label": "a New Jersey public agency",
        "note": "Statewide registrations and wage rules apply to most New Jersey public agency work.",
        _CONSTRUCTION: ("NJSTART Vendor Registration", "Required Public Contract Forms Guide"),
        _PROFESSIONAL: ("NJSTART Vendor Registration",),
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


def readiness_for(record: dict[str, Any], limit: int = 8) -> dict[str, Any] | None:
    """Return the bid-readiness pack for one opportunity, or None if nothing applies.

    The limit accommodates an agency block plus the full federal-aid set: on a
    federally funded job, Buy America changes material sourcing, so it must not
    be the entry that truncation drops.
    """
    track_key = _track(str(record.get("source_id") or ""))
    track = _TRACKS.get(track_key)
    if not track:
        return None

    record_type = record.get("record_type") or record.get("notice_type")
    audience_key = _PROFESSIONAL if record_type == _PROFESSIONAL else _CONSTRUCTION
    titles = list(track.get(audience_key) or ())

    # Federal-aid rules bind the bid harder than the generic State baseline, so
    # they are ordered ahead of it rather than being truncated away by the limit.
    if _looks_federally_funded(record) or track_key == "njtransit":
        titles.extend(_FEDERAL_AID)

    if "caveat" not in track:
        # NJ State and local baseline requirements, after the agency-specific items.
        for title in _NJ_STATE_BASELINE:
            entry = _BY_TITLE.get(title)
            if not entry:
                continue
            if entry["audience"] == "Construction" and audience_key != _CONSTRUCTION:
                continue
            titles.append(title)

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
        # Not "items": Jinja resolves ``pack.items`` to the dict method first.
        "resources": resources,
    }
