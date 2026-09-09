"""Shared public scan rules; source dates and statuses remain untouched."""

import re
from datetime import datetime

from app.core.deadlines import EASTERN, deadline_days_remaining, deadline_is_past
from app.core.corridors import normalize_search_routes


# Search vocabulary only: these associations must never classify a notice or
# become map/geography evidence. Require whole phrases in project text, not
# agency names (e.g. a stormwater utility purchasing office furniture).
_TRADE_SEARCH = {
    "paving": ("resurfacing", "resurface", "pavement preservation", "pavement rehabilitation", "pavement reconstruction", "asphalt overlay", "road milling"),
    "resurfacing": ("resurface", "paving", "pavement preservation", "asphalt overlay"),
    "drainage": ("culvert", "culverts", "stormwater", "storm water", "storm sewer", "storm sewers"),
    "bridge": ("bridges", "viaduct", "viaducts"),
    "culvert": ("culverts",),
}


def _trade_search_tokens(record):
    found = set()
    for field in ("title", "notice_excerpt"):
        text = " " + " ".join(re.findall(r"[a-z0-9]+", str(record.get(field) or "").casefold())) + " "
        for query_token, phrases in _TRADE_SEARCH.items():
            if any(" " + phrase + " " in text for phrase in phrases):
                found.add(query_token)
    return found


def closing_soon(record, now=None):
    now = now or datetime.now(EASTERN)
    days = deadline_days_remaining(record, now)
    return bool(
        record.get("status") == "open"
        and not record.get("deadline_conflict")
        and days is not None and 0 <= days <= 7
        and not deadline_is_past(record, now)
    )


def matches_search(record, query):
    def tokens(value):
        text = normalize_search_routes(str(value or '').casefold())
        text = re.sub(r'\bdp[\s.-]*(?:no\.?\s*)?(\d+)\b', r'dp \1', text)
        return re.findall(r"[a-z0-9]+", text)

    values = [record.get(key) for key in (
        "title", "notice_excerpt", "source_name", "contract_number", "county_display"
    )]
    for key in ("corridors", "municipalities", "road_names"):
        values.extend(record.get(key) or [])
    haystack = {token for value in values for token in tokens(value)}
    haystack.update(token for value in values for token in re.findall(r'[a-z0-9]+', str(value or '').casefold()))
    haystack.update(_trade_search_tokens(record))
    contract = re.sub(r'[^a-z0-9]', '', str(record.get('contract_number') or '').casefold())
    if contract:
        haystack.add(contract)
    return all(token in haystack for token in tokens(query))


def first_seen_today(record, now=None):
    value = record.get("first_seen_at")
    if not value:
        return False
    try:
        first = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if first.tzinfo is None:
            return False
        return first.astimezone(EASTERN).date() == (now or datetime.now(EASTERN)).astimezone(EASTERN).date()
    except (TypeError, ValueError):
        return False
