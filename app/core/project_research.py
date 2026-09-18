"""Small NJDOT research packs; reference routing, never project-data enrichment."""
import re

from app.core.corridors import classify_location
from app.core.project_maps import project_map_links


REVIEWED_ON = "2026-09-17"
PILOT_SOURCES = frozenset({
    "state-njdot-construction", "state-njdot-profserv",
    "state-njdot-profserv-upcoming", "state-njdot-design-build",
})
DOT = "https://dot.nj.gov/transportation/"


def _link(key, label, url):
    return {"key": key, "label": label, "url": url}


TOOLS = {
    "road": {
        "title": "Roadway views and cameras",
        "description": "NJDOT roadway diagrams and imagery, plus the public 511NJ camera directory. "
                       "Select the road and check image dates. Camera coverage of this project has not been verified.",
        "links": [
            _link("roadway_views", "Open roadway diagrams and imagery", DOT + "refdata/sldiag/"),
            _link("traffic_cameras", "Browse public traffic cameras", "https://511nj.org/camera"),
        ],
    },
    "traffic": {
        "title": "Traffic volumes",
        "description": "NJDOT traffic-count and AADT mapping. Match the road segment and count year; "
                       "these are traffic references, not permitted lane-closure hours.",
        "links": [_link("traffic_counts", "Find traffic counts", DOT + "refdata/gis/arcgis.shtm")],
    },
    "prices": {
        "title": "Historical bid pricing",
        "description": "NJDOT's estimation references and bid-price reports. Compare item units, quantities "
                       "and report dates; historical prices are not supplier quotes or this project's estimate.",
        "links": [_link("bid_prices", "Review bid-price references", DOT + "business/aashtoware/estimation.shtm")],
    },
    "index": {
        "title": "Asphalt and fuel indices",
        "description": "Published NJDOT indices by effective period and applicable region. "
                       "Check this contract's adjustment provisions; an index is not a delivered-material quote.",
        "links": [_link("asphalt_fuel", "Check asphalt and fuel indices", DOT + "business/aashtoware/PriceIndex.shtm")],
    },
    "borings": {
        "title": "Subsurface background",
        "description": "NJDOT's map search for boring logs and location plans. Historical or nearby records "
                       "are background only, not this contract's geotechnical investigation.",
        "links": [_link("soil_borings", "Search historical borings", DOT + "refdata/geologic/index.shtml")],
    },
    "environment": {
        "title": "Environmental context",
        "description": "NJDEP's environmental layers and aerial imagery. Locate the project in the viewer; "
                       "mapped features do not establish permit requirements or confirmed site conditions.",
        "links": [_link("environmental_viewer", "Explore NJ-GeoWeb", "https://dep.nj.gov/gis/nj-geoweb/")],
    },
    "consultant": {
        "title": "NJDOT consultant procurement",
        "description": "The professional-services track and technical-proposal instructions. "
                       "The current solicitation and addenda control the required contents and delivery method.",
        "links": [
            _link("consultant_track", "Review the consultant procurement track", DOT + "business/procurement/ProfServ/"),
            _link("technical_proposals", "Check technical-proposal instructions", DOT + "business/procurement/ProfServ/techprop.shtm"),
        ],
    },
}


def research_for(record):
    """Select at most four tool groups without asserting location or eligibility.

    Match titles only: receipt addresses and agency boilerplate in notice bodies
    must not produce project locations. Professional-service type takes priority
    over construction words in forecasts. No network requests occur on page load.
    """
    if record.get("source_id") not in PILOT_SOURCES:
        return None
    if record.get("status") not in ("open", "upcoming", "expired", "unknown_date"):
        return None
    kind = record.get("record_type") or record.get("notice_type")
    if kind not in ("construction", "professional_services"):
        return None
    title = str(record.get("title") or "")
    text = re.sub(r"[^a-z0-9]+", " ", title.lower())
    location = classify_location({"title": title})
    roadway = bool(location["corridors"] or location["road_names"])
    paving = bool(re.search(r"\b(?:paving|resurfacing|asphalt|pavement preservation|milling)\b", text))
    structure = bool(re.search(r"\b(?:bridges?|culverts?|drainage|stormwater|basin restoration)\b", text))
    environmental = bool(re.search(r"\b(?:remediation|environmental|dredging|geotechnical)\b", text))

    keys = []
    if kind == "professional_services":
        keys.append("consultant")
    if roadway or paving:
        keys.append("road")
    if structure or environmental:
        keys.extend(["borings", "environment"])
    elif paving and kind == "construction":
        keys.extend(["traffic", "prices", "index"])
    elif roadway or re.search(r"\b(?:aadt|traffic counts?|traffic data)\b", text):
        keys.append("traffic")

    # Mixed paving/structure scopes prioritize site context, not a guessed trade.
    groups = [{**TOOLS[key], "key": key} for key in dict.fromkeys(keys)]
    # Reuse only reviewed structure evidence, never an arbitrary notice-body URL.
    for link in project_map_links(record):
        if link.get("kind") == "verified_structure" and link.get("evidence_url"):
            groups.insert(1 if kind == "professional_services" else 0, {
                "key": "background", "title": "Published project background",
                "description": "NJDOT's project flyer for " + link["name"] +
                               ". Background may predate this solicitation; current plans and addenda control.",
                "links": [_link("project_background", "Read the NJDOT project flyer", link["evidence_url"])],
            })
            break
    groups = groups[:4]
    if not groups:
        return None
    return {"groups": groups, "reviewed_on": REVIEWED_ON,
            "context": ", ".join(location["corridors"] + location["road_names"]),
            "note": "Official reference tools, not project-specific findings. Viewers open without a selected site; "
                    "use the project limits in the official plans."}
