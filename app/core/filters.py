from __future__ import annotations

import re
from datetime import datetime, timezone

TITLE_BLOCKLIST_PREFIXES = [
    "website sign in",
    "staff directory",
    "built to help vendors",
    "in order to maintain a current list",
    "contract documents",
    "contract awards",
    "professional services / current procurements",
    "professional services upcoming procurements",
    "notice to contractors home /",
    "rfb's (request for bids) awarded",
    "rfb's (request for bids) upcoming",
    "rfpq's (request for professional",
    "results of bid/rfp openings",
    "contract compliance",
    "project (completed",
    "project southern operations",
    "project washington crossing",
]

TITLE_BLOCKLIST_SUBSTRINGS = [
    "how do i search home departments",
    "finance & administration purchasing bid solicitations",
]

MIN_TITLE_LENGTH = 15

ZERO_WIDTH_CHARS = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")


def clean_title(title: str | None) -> str:
    if not title:
        return ""
    title = ZERO_WIDTH_CHARS.sub("", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def is_garbage_title(title: str | None) -> bool:
    if not title:
        return True
    cleaned = clean_title(title)
    lower = cleaned.lower()
    if len(cleaned) < MIN_TITLE_LENGTH:
        return True
    for prefix in TITLE_BLOCKLIST_PREFIXES:
        if lower.startswith(prefix):
            return True
    for substring in TITLE_BLOCKLIST_SUBSTRINGS:
        if substring in lower:
            return True
    return False


def is_expired(due_at: datetime | None) -> bool:
    if due_at is None:
        return False
    now = datetime.now(timezone.utc)
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    return due_at < now


def is_stale_no_date(created_at: datetime | None, days: int = 180) -> bool:
    if created_at is None:
        return False
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return (now - created_at).days > days


def should_reject_lead(
    title: str | None,
    due_at: datetime | None = None,
    created_at: datetime | None = None,
) -> tuple[bool, str]:
    if is_garbage_title(title):
        return True, f"Rejected: garbage title — '{clean_title(title)[:80]}'"
    if due_at is not None and is_expired(due_at):
        return True, f"Rejected: due date {due_at.date()} is in the past"
    if due_at is None and is_stale_no_date(created_at, days=180):
        return True, "Rejected: no due date and record is over 180 days old"
    return False, ""
