"""Shared public scan rules; source dates and statuses remain untouched."""

import re
from datetime import datetime

from app.core.deadlines import EASTERN, deadline_days_remaining, deadline_is_past


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
        return re.findall(r"[a-z0-9]+", str(value or "").casefold())

    values = [record.get(key) for key in (
        "title", "notice_excerpt", "source_name", "contract_number", "county_display"
    )]
    for key in ("corridors", "municipalities", "road_names"):
        values.extend(record.get(key) or [])
    haystack = {token for value in values for token in tokens(value)}
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
