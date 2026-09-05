"""Normalize procurement deadlines without discarding source text."""

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")
UNKNOWN_VALUES = {"", "not listed", "unknown", "n/a", "-", "\u2014"}
DATE_FORMATS = (
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d-%b-%Y",
    "%b. %d, %Y",
    "%B %d %Y",
    "%Y-%m-%d",
)
DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%y %I:%M:%S %p",
    "%m/%d/%y %I:%M %p",
)
MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|"
    r"Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\."
)
WINDOW_PATTERN = re.compile(
    r"(?:spring|summer|fall|autumn|winter|early|late|anticipated|expected|"
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s*/)",
    re.I,
)


def _display_date(value: date) -> str:
    return value.strftime("%a, %b %d, %Y").replace(" 0", " ")


def _display_datetime(value: datetime) -> str:
    local = value.astimezone(EASTERN)
    rendered = local.strftime("%a, %b %d, %Y at %I:%M %p").replace(" 0", " ")
    return f"{rendered} ET"


def format_eastern_timestamp(value: str | None) -> str | None:
    """Format an ISO crawl timestamp in explicit Eastern time."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return _display_datetime(parsed)


def _parse_date(value: str) -> date | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(value: str) -> tuple[datetime | None, str | None, bool]:
    """Return parsed datetime, timezone provenance, and assumption flag."""
    iso_value = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", iso_value):
        try:
            parsed = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed:
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=EASTERN), "assumed_eastern", True
            return parsed, "source_offset", False

    explicit_utc = bool(re.search(r"\b(?:UTC|GMT)\b", value, re.I))
    explicit_eastern = bool(
        re.search(r"\b(?:ET|EST|EDT)\b|Eastern\s+Time", value, re.I)
    )
    cleaned = re.sub(r"\s*(?:Eastern\s+Time(?:\s*\(ET\))?|ET|EST|EDT|UTC|GMT)\s*$", "", value, flags=re.I)

    for fmt in DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            if explicit_utc:
                return parsed.replace(tzinfo=timezone.utc), "explicit_utc", False
            if explicit_eastern:
                return parsed.replace(tzinfo=EASTERN), "explicit_eastern", False
            return parsed.replace(tzinfo=EASTERN), "assumed_eastern", True
        except ValueError:
            continue

    date_match = re.search(rf"({MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(\d{{4}})", value, re.I)
    time_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM))", value, re.I)
    if date_match and time_match:
        date_text = date_match.group(0)
        time_text = time_match.group(1)
        parsed_date = None
        for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
            try:
                parsed_date = datetime.strptime(date_text.replace(".", ""), fmt.replace(".", "")).date()
                break
            except ValueError:
                continue
        if parsed_date:
            time_fmt = "%I:%M:%S %p" if time_text.count(":") == 2 else "%I:%M %p"
            parsed_time = datetime.strptime(time_text.upper(), time_fmt).time()
            parsed = datetime.combine(parsed_date, parsed_time)
            if explicit_utc:
                return parsed.replace(tzinfo=timezone.utc), "explicit_utc", False
            if explicit_eastern:
                return parsed.replace(tzinfo=EASTERN), "explicit_eastern", False
            return parsed.replace(tzinfo=EASTERN), "assumed_eastern", True

    return None, None, False


def normalize_deadline(record: dict, today: date | None = None) -> dict:
    """Add normalized deadline fields to a record in place and return it."""
    raw_value = record.get("due_date_raw") or record.get("due_date") or ""
    raw = str(raw_value).strip()
    record["due_date_raw"] = raw
    today = today or datetime.now(EASTERN).date()

    record.update(
        deadline_at=None,
        deadline_local=None,
        deadline_timezone=None,
        deadline_timezone_source=None,
        deadline_timezone_assumed=False,
        deadline_has_time=False,
        deadline_precision="unknown",
        deadline_display="Deadline not published",
        due_date_parsed=None,
        days_until_due=None,
        deadline_conflict=False,
        published_deadline_display=None,
    )
    if raw.lower() in UNKNOWN_VALUES:
        return record

    cleaned = re.sub(r"^(?:open|closed|advertised|pending)\s*[:\-]?\s*", "", raw, flags=re.I).strip()
    parsed_datetime, timezone_source, assumed = _parse_datetime(cleaned)
    if parsed_datetime:
        local = parsed_datetime.astimezone(EASTERN)
        utc = parsed_datetime.astimezone(timezone.utc)
        record.update(
            deadline_at=utc.isoformat().replace("+00:00", "Z"),
            deadline_local=local.isoformat(),
            deadline_timezone="America/New_York",
            deadline_timezone_source=timezone_source,
            deadline_timezone_assumed=assumed,
            deadline_has_time=True,
            deadline_precision="datetime",
            deadline_display=_display_datetime(parsed_datetime) + (" (time zone assumed)" if assumed else ""),
            due_date_parsed=local.date().isoformat(),
            days_until_due=(local.date() - today).days,
        )
        return record

    parsed_date = _parse_date(cleaned)
    if parsed_date:
        record.update(
            deadline_precision="date",
            deadline_display=f"{_display_date(parsed_date)} (time not published)",
            due_date_parsed=parsed_date.isoformat(),
            days_until_due=(parsed_date - today).days,
        )
        return record

    if record.get("is_planned") or record.get("status") == "upcoming" or WINDOW_PATTERN.search(cleaned):
        record.update(
            deadline_precision="window",
            deadline_display=f"{raw} (anticipated)",
        )
    else:
        record["deadline_display"] = f"{raw} (unparsed - verify with agency)"
    return record


def deadline_date(record: dict) -> date | None:
    value = record.get("due_date_parsed")
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def eastern_today():
    return datetime.now(EASTERN).date()


def deadline_days_remaining(record: dict, now: datetime | date | None = None) -> int | None:
    """Count Eastern calendar dates, not elapsed 24-hour periods."""
    due = deadline_date(record)
    if not due:
        return None
    if isinstance(now, date) and not isinstance(now, datetime):
        today = now
    else:
        current = now or datetime.now(EASTERN)
        if current.tzinfo is None:
            current = current.replace(tzinfo=EASTERN)
        today = current.astimezone(EASTERN).date()
    return (due - today).days


def reconcile_authoritative_open_deadline(
    record: dict,
    now: datetime | None = None,
) -> bool:
    """Keep an authoritative Open record live while disclosing a stale deadline."""
    source_status = str(record.get("source_status") or "").strip().lower()
    if not record.get("source_status_authoritative") or source_status != "open":
        return False
    if not deadline_is_past(record, now):
        return False

    published_display = record.get("deadline_display") or "Published closing date"
    record.update(
        deadline_conflict=True,
        published_deadline_display=published_display,
        deadline_display=(
            f"{published_display} - agency currently lists this opportunity as Open; "
            "verify the closing date"
        ),
        days_until_due=None,
    )
    return True


def deadline_is_past(record: dict, now: datetime | None = None) -> bool:
    """Use the exact instant when published; otherwise expire after the local date."""
    now = now or datetime.now(EASTERN)
    if now.tzinfo is None:
        now = now.replace(tzinfo=EASTERN)
    if record.get("deadline_at"):
        try:
            parsed = datetime.fromisoformat(record["deadline_at"].replace("Z", "+00:00"))
            return now.astimezone(timezone.utc) > parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass
    due = deadline_date(record)
    return bool(due and due < now.astimezone(EASTERN).date())
