"""Health evaluation for configured bid crawler sources."""

from collections import Counter
from datetime import datetime, timezone
from statistics import median


NJ_COUNTIES = {
    "Atlantic", "Bergen", "Burlington", "Camden", "Cape May", "Cumberland",
    "Essex", "Gloucester", "Hudson", "Hunterdon", "Mercer", "Middlesex",
    "Monmouth", "Morris", "Ocean", "Passaic", "Salem", "Somerset",
    "Sussex", "Union", "Warren",
}

STALE_AFTER_HOURS = {
    "daily": 48,
    "weekly": 216,
}


def _parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _prior_positive_counts(entry):
    history = entry.get("history") or []
    if history:
        history = history[:-1]
    return [
        item.get("count")
        for item in history
        if not item.get("error") and isinstance(item.get("count"), int) and item["count"] > 0
    ]


def evaluate_source(source, entry=None, now=None):
    """Return a stable health record for one configured source."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    entry = entry or {}
    critical = bool(source.get("critical"))
    frequency = source.get("crawl_freq", "weekly")
    stale_after = STALE_AFTER_HOURS.get(frequency, STALE_AFTER_HOURS["weekly"])
    last_crawl = _parse_datetime(entry.get("last_crawl"))
    last_count = entry.get("last_count")
    last_error = entry.get("last_error")
    history = entry.get("history") or []

    consecutive_failures = 0
    for item in reversed(history):
        if item.get("error"):
            consecutive_failures += 1
        else:
            break

    ever_produced = (isinstance(last_count, int) and last_count > 0) or any(
        not item.get("error") and isinstance(item.get("count"), int) and item["count"] > 0
        for item in history
    )

    result = {
        "source_id": source["id"],
        "source_name": source["name"],
        "url": source["url"],
        "crawl_tier": source.get("crawl_tier"),
        "source_tier": source.get("source_tier"),
        "frequency": frequency,
        "parser": source.get("parser", "generic_html_list"),
        "critical": critical,
        "access_state": source.get("crawl_state", "accessible"),
        "access_reason": source.get("access_reason"),
        "last_crawl": entry.get("last_crawl"),
        "last_successful_crawl": entry.get("last_successful_crawl"),
        "last_count": last_count,
        "last_error": last_error,
        "consecutive_failures": consecutive_failures,
        "ever_produced": ever_produced,
        "baseline_count": None,
        "status": "ok",
        "severity": "ok",
        "message": "Latest crawl completed normally.",
    }

    if source.get("crawl_state") == "inaccessible":
        result.update(
            status="inaccessible",
            severity="warning",
            last_error=None,
            consecutive_failures=0,
            message=source.get("access_reason", "This source cannot be crawled anonymously."),
        )
        return result

    # Source policy can change after a crawl. Reclassify a stored empty-result
    # error when the source is now explicitly allowed to have no matching bids.
    if last_error == "zero_records" and source.get("allow_empty"):
        last_error = None
        result["last_error"] = None
        result["consecutive_failures"] = 0

    if not last_crawl:
        result.update(
            status="never_run",
            severity="error" if critical else "warning",
            message="No crawl has been recorded for this configured source.",
        )
        return result

    age_hours = round((now - last_crawl).total_seconds() / 3600, 1)
    result["age_hours"] = max(age_hours, 0)
    if age_hours > stale_after:
        result.update(
            status="stale",
            severity="error" if critical else "warning",
            message=f"Last crawl is {int(age_hours)} hours old; expected every {frequency} cycle.",
        )
        return result

    if last_error:
        if last_error == "zero_records":
            message = "Crawler returned no records where at least one was expected."
        else:
            message = f"Latest crawl failed: {last_error}"
        result.update(status="error", severity="error", message=message)
        return result

    prior_counts = _prior_positive_counts(entry)
    if len(prior_counts) >= 3:
        baseline = median(prior_counts[-10:])
        result["baseline_count"] = baseline
        if baseline >= 5 and isinstance(last_count, int) and last_count < baseline * 0.35:
            result.update(
                status="count_drop",
                severity="warning",
                message=f"Record count fell from a {baseline:g} baseline to {last_count}.",
            )
            return result

    if last_count == 0 and source.get("allow_empty"):
        if ever_produced:
            result["message"] = "Crawl succeeded; no matching opportunities are currently listed."
        else:
            # Zero is allowed by source policy, but a source that has never once
            # produced a record gives no evidence its parser can see the page's
            # listings. Keep the status honest without raising an alarm.
            result["message"] = (
                "Crawl succeeded with no matching opportunities; this source has "
                "never produced a record, so an unnoticed parser mismatch cannot "
                "be ruled out."
            )
    return result


def build_health_summary(sources, crawl_log, now=None, notices=None):
    """Build health and source-coverage metrics for all configured sources."""
    now = now or datetime.now(timezone.utc)
    log_by_id = {entry.get("source_id"): entry for entry in crawl_log}
    evaluated = [evaluate_source(source, log_by_id.get(source["id"]), now) for source in sources]
    evaluated.sort(key=lambda item: (item["crawl_tier"] or 9, item["source_name"].lower()))

    severity_counts = Counter(item["severity"] for item in evaluated)
    status_counts = Counter(item["status"] for item in evaluated)
    critical_failures = [item for item in evaluated if item["critical"] and item["severity"] == "error"]

    county_source_ids = {}
    for source in sources:
        if source.get("source_tier") == "county" and source.get("county") in NJ_COUNTIES:
            county_source_ids.setdefault(source["county"], []).append(source["id"])
    configured_counties = set(county_source_ids)
    missing_counties = sorted(NJ_COUNTIES - configured_counties)

    # Configured-source coverage says nothing about whether a county's crawler
    # can actually read its page. Track record-level coverage separately:
    # counties whose sources have never yielded a record, and (when the notice
    # set is supplied) how many active records each county source contributes.
    evaluated_by_id = {item["source_id"]: item for item in evaluated}
    counties_never_produced = sorted(
        county
        for county, source_ids in county_source_ids.items()
        if not any(
            evaluated_by_id[source_id].get("ever_produced") for source_id in source_ids
        )
    )
    county_active_records = None
    counties_without_active_records = None
    if notices is not None:
        active_by_source = Counter(
            notice.get("source_id")
            for notice in notices
            if not notice.get("source_inactive")
        )
        county_active_records = {
            county: sum(active_by_source[source_id] for source_id in source_ids)
            for county, source_ids in sorted(county_source_ids.items())
        }
        counties_without_active_records = sorted(
            county for county, count in county_active_records.items() if count == 0
        )
    tier_counts = Counter(str(source.get("crawl_tier", "unknown")) for source in sources)
    frequency_counts = Counter(source.get("crawl_freq", "unknown") for source in sources)
    active_review_records = [
        notice for notice in (notices or [])
        if not notice.get("source_inactive")
        and (notice.get("geography_review_required") or notice.get("parser_review_required"))
    ]
    review_by_source = Counter(notice.get("source_id", "unknown") for notice in active_review_records)

    overall = (
        "error" if critical_failures
        else "warning" if severity_counts["error"] or severity_counts["warning"] or active_review_records
        else "ok"
    )
    return {
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "overall": overall,
        "configured_sources": len(sources),
        "healthy_sources": severity_counts["ok"],
        "warning_sources": severity_counts["warning"],
        "error_sources": severity_counts["error"],
        "critical_failures": len(critical_failures),
        "status_counts": dict(status_counts),
        "data_quality": {
            "active_records_requiring_segmentation_review": len(active_review_records),
            "segmentation_review_by_source": dict(review_by_source),
        },
        "coverage": {
            "county_sources": len(configured_counties),
            "counties_expected": len(NJ_COUNTIES),
            "missing_counties": missing_counties,
            "counties_never_produced": counties_never_produced,
            "county_active_records": county_active_records,
            "counties_without_active_records": counties_without_active_records,
            "by_tier": dict(tier_counts),
            "by_frequency": dict(frequency_counts),
        },
        "sources": evaluated,
    }
