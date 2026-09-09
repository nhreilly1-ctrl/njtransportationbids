"""Evidence-backed map destinations, separate from notice geography fields."""

import re
from urllib.parse import quote_plus

from app.core.corridors import classify_location, _map_county_context


# Reviewed against the official project flyer, not Google's search ranking.
# Matching requires the agency, route, direction and named crossing together.
VERIFIED_STRUCTURES = ({
    "name": "Morris Goodkind Bridge",
    "source_prefix": "state-njdot-",
    "route": "US-1 NB",
    "crossing": "bridge over raritan river",
    "url": "https://www.google.com/maps/place/Morris+Goodkind+Bridge/data=!4m7!3m6!1s0x89c3c62e972e78d1:0xeb2716eb2454409e!8m2!3d40.4926175!4d-74.4129502!16zL20vMGY4dmNo",
    "evidence_url": "https://www.nj.gov/transportation/uploads/comm/pubmeet/details/Handbook_20240123_152106_2024-01Rt1NBoverRaritan-PICFlyerEnglish.pdf",
    "reviewed_at": "2026-09-09",
},)


def project_map_links(record):
    """Return independent map actions; never enrich counties or invent a pin.

    General notice bodies contain receipt offices and prebid meeting addresses.
    Until project-location spans are explicitly modeled, only title locations
    qualify. Agency county context is a search qualifier, not location evidence.
    """
    title = str(record.get("title") or "")
    location = classify_location({"title": title})
    roads = location["road_names"]
    routes = location["corridors"]
    crossings = location["crossing_phrases"]
    for structure in VERIFIED_STRUCTURES:
        if (
            str(record.get("source_id") or "").startswith(structure["source_prefix"])
            and location["directional_corridors"] == [structure["route"]]
            and routes == ["US-1"]
            and not roads
            and [x.casefold() for x in crossings] == [structure["crossing"]]
        ):
            return [{**structure, "kind": "verified_structure",
                     "label": "View " + structure["name"],
                     "query": structure["name"] + ", New Jersey",
                     "note": "Structure identity checked against NJDOT. Contract limits and site access must be confirmed in the plans."}]

    municipalities = list({name.casefold(): name for name in reversed(location["municipalities"])}.values())
    # The general extractor can see both "City of Ocean City" and "Ocean
    # City" in one phrase. Prefer its leading municipal form, not two places.
    municipalities = [name for name in municipalities if not any(
        other != name and other.endswith(" of " + name) for other in municipalities
    )]
    counties = record.get("counties") or []
    if record.get("geography_provenance") in ("NOTICE_TEXT", "SOURCE_RECORD_FIELD") and len(counties) > 1:
        context = []  # Do not pair every route with an arbitrary county.
    elif len(municipalities) == 1:
        context = municipalities
    else:
        county = _map_county_context(record)
        context = [county] if county else []

    # Road names are safer than redundant CR numbers (601 becomes a house
    # number). Separate named roads preserve all choices without inventing
    # intersections or cross-street pairings from an unstructured list.
    intersection = (
        len(roads) in (2, 3)
        and re.search(r"\bintersection\b", title, re.I)
        and re.search(re.escape(roads[0]) + r"\s*\)?\s+(?:and|&)\s+" + re.escape(roads[1]), title, re.I)
        and (len(roads) == 2 or re.search(re.escape(roads[1]) + r"\s*/\s*" + re.escape(roads[2]), title, re.I))
    )
    if intersection:
        targets = [roads[0] + " & " + road for road in roads[1:]]
        kind, verb = "intersection_search", "Search intersection"
    elif roads:
        targets = roads
        kind, verb = "road_search", "Search road"
    elif crossings and len(routes) == 1:
        targets = [", ".join((location["directional_route_labels"] or routes)[:1] + crossings)]
        kind, verb = "location_search", "Search project location"
    elif routes:
        targets = routes
        kind, verb = "corridor_search", "View corridor"
    else:
        return []
    links = []
    for target in dict.fromkeys(targets):
        query = ", ".join([target, *context, "New Jersey"])
        links.append({"kind": kind, "query": query,
                      "url": "https://www.google.com/maps/search/?api=1&query=" + quote_plus(query),
                      "label": verb + (": " + target if len(targets) > 1 else ""),
                      "note": "Map search, not a verified project pin or work limits. Confirm the location in the official plans."})
    return links
