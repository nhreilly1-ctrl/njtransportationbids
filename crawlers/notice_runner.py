"""
notice_runner.py
----------------
Main crawl orchestrator. Run this daily via GitHub Actions.

Usage:
    python notice_runner.py                  # crawl daily sources
    python notice_runner.py --weekly         # crawl weekly sources too
    python notice_runner.py --tier 1         # crawl only state agencies
    python notice_runner.py --source state-njdot-construction  # one source
    python notice_runner.py --seed-sos       # refresh Tier 3 municipal seed

Output:
    data/notices/notices.json         — all active notices (merged, deduped)
    data/notices/crawl_log.json       — per-source crawl health log
    data/notices/sos_entities.json    — discovered municipal notice pages
"""

import os, json, sys, argparse, logging, hashlib
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from notice_sources import (
    NOTICE_SOURCES, TIER1_SOURCES, TIER2_SOURCES,
    TIER3_SOURCES, TIER4_SOURCES, DAILY_SOURCES, WEEKLY_SOURCES,
    SOURCES_BY_ID
)
from notice_crawlers import crawl_source, parse_sos_directory, parse_municipal_from_sos
from source_health import build_health_summary
from app.core.deadlines import (
    deadline_date,
    deadline_is_past,
    normalize_deadline,
    reconcile_authoritative_open_deadline,
)
from app.core.corridors import enrich_location
from app.core.geography import enrich_geography

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("notice_runner")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE         = Path(__file__).parent.parent
DATA_DIR     = BASE / "data" / "notices"
NOTICES_F    = DATA_DIR / "notices.json"
CRAWL_LOG_F  = DATA_DIR / "crawl_log.json"
HEALTH_F     = DATA_DIR / "health_summary.json"
SOS_ENT_F    = DATA_DIR / "sos_entities.json"
OPP_F        = BASE / "data" / "opportunities.json"   # legacy file for merge

AUTHORITATIVE_PARSERS = {
    "njdot_construction",
    "njdot_profserv",
    "njdot_profserv_upcoming",
    "njdot_design_build",
    "njta",
    "njtransit",
    "drjtbc",
    "sjta",
    "passaic_bids",
    "panynj",
    "drpa",
    "njtpa",
    "essex_county",
    "camden_county",
    "monmouth_county",
    "gloucester_county",
    "opengov",
    "bidnet_agency",
    "bonfire",
    "ionwave",
    "hudson_county",
    "union_county",
    "newark_water",
    "somerset_county",
    "warren_county",
    "salem_county",
}

DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── Data helpers ──────────────────────────────────────────────────────────────

def _load(path):
    if not path.exists(): return []
    with open(path, encoding="utf-8") as f: return json.load(f)

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

def _now():
    return datetime.now(timezone.utc).isoformat()

def _today():
    return date.today().isoformat()


# ── Deduplication ─────────────────────────────────────────────────────────────

def _dedupe(notices):
    """
    Remove duplicates. Priority:
    1. Exact ID match — keep newer crawled_at
    2. Same (source_id + contract_number) — keep newer
    3. Same normalized title within a source — keep newer
    """
    # Prefer a currently observed record over an inactive historical copy,
    # then prefer the newest crawl. This matters when a parser improvement
    # changes an ID while retaining the same agency contract number.
    ordered = sorted(
        notices,
        key=lambda item: (
            not item.get("source_inactive", False),
            item.get("crawled_at", ""),
        ),
        reverse=True,
    )
    deduped = []
    seen_ids = set()
    seen_contracts = set()
    seen_titles = set()
    for n in ordered:
        nid = n.get("id","")
        src = n.get("source_id","")
        cno = (n.get("contract_number_match") or n.get("contract_number","") or "").strip().upper()
        ck  = f"{src}:{cno}" if cno else None
        normalized_title = " ".join((n.get("title") or "").lower().split())
        title_key = f"{src}:{normalized_title}"

        if nid in seen_ids:
            continue
        if ck and ck in seen_contracts:
            continue
        if normalized_title and title_key in seen_titles:
            continue

        seen_ids.add(nid)
        if ck:
            seen_contracts.add(ck)
        if normalized_title:
            seen_titles.add(title_key)
        deduped.append(n)

    return deduped


# ── Enrichment ────────────────────────────────────────────────────────────────

def _enrich(n, now=None):
    """Compute status, days_until_due, preserve manual overrides."""
    enrich_geography(n)
    enrich_location(n)
    today = now.date() if now is not None else None
    normalize_deadline(n, today=today)
    deadline_conflict = reconcile_authoritative_open_deadline(n, now)

    # Respect admin overrides
    if n.get("status_override") in ("approved","noise","deleted"):
        n["status"] = n["status_override"]
        return n

    due = deadline_date(n)

    source_status = (n.get("source_status") or "").strip().lower()

    # Status
    if n.get("noise_flagged") or n.get("status_override") == "noise":
        n["status"] = "noise"
    elif n.get("source_inactive"):
        n["status"] = "expired"
    elif n.get("geography_review_required") or n.get("parser_review_required"):
        n["status"] = "review_required"
    elif source_status in ("closed", "awarded", "cancelled", "canceled", "withdrawn"):
        n["status"] = "expired"
    elif n.get("is_planned") or source_status in ("upcoming", "planned", "anticipated"):
        n["status"] = "upcoming"
    elif deadline_conflict:
        n["status"] = "open"
    elif deadline_is_past(n, now):
        n["status"] = "expired"
    elif due:
        n["status"] = "open"
    elif source_status in ("open", "advertised", "current"):
        n["status"] = "open"
    else:
        n["status"] = "unknown_date"

    # Urgency flag
    n["urgent"] = (
        due is not None
        and n["status"] == "open"
        and not n.get("deadline_conflict")
        and n.get("days_until_due") is not None
        and n["days_until_due"] <= 7
    )

    return n


# ── Noise filter (notices version) ────────────────────────────────────────────

NOTICE_NOISE_PHRASES = [
    "staff directory","vendor portal","sign in","how do i",
    "website sign","government departments","built to help",
    "trip planningtoll calculator","safetripnj app","forms & records",
    "accident report request","traffic permits","learn more.",
    "traffic information. get the app","design, supervision, environmental",
    "services for the njta and troop d","bid results",
    "nj dept. of transportation procurement division",
    "key to saving money with e","upcoming rfpq","awarded rfp",
    "legal notice regarding online public notices",
    "roadway, bridge, facility, and other construction",
    "goods and non-engineering services for the njta",
    "provide comment on the delaware river joint toll bridge",
    "archive of bids","results of bid","contract awards",
    "procurement calendar","current legal notices page",
    "please take notice that pursuant to p.l. 2025",  # announcement notices
    "legal notices will be posted","notices can be found",
]

OUT_OF_SCOPE_NOTICES = [
    "harley","davidson","motorcycle","cannabis","housing rehab",
    "septic","eeoc investigation","affordable housing",
    "exhibition design","black heritage","historic marker",
    "ev charging station","electric vehicle charging",
    "health benefits program","self-funded health",
    "animal control","recreation","park maintenance",
    "refuse collection","solid waste","trash collection",
    "extra heavy duty towing","broker dealer","electronic surveillance",
]

def _is_noise(n):
    title = (n.get("title") or "").lower()
    excerpt = (n.get("notice_excerpt") or "").lower()
    text = title + " " + excerpt

    if n.get("scope_excluded"):
        reason = n.get("scope_exclusion_reason") or "published category"
        return True, f"out of scope: {reason}"
    if len(title.split()) < 5:
        return True, "title too short"
    for p in NOTICE_NOISE_PHRASES:
        if p in text:
            return True, f"noise phrase: {p}"
    for k in OUT_OF_SCOPE_NOTICES:
        if k in title:
            if (
                n.get("source_id") == "state-njta"
                and n.get("notice_subtype") == "roadway_support_services"
                and k == "extra heavy duty towing"
            ):
                continue
            return True, f"out of scope: {k}"
    return False, ""


# ── Merge with existing notices ───────────────────────────────────────────────

def _merge(existing, fresh, refreshed_source_ids=None):
    """
    Merge fresh crawl results into existing notices.
    - Preserve manual overrides (status_override, noise_flagged)
    - Update crawled_at and notice_excerpt for existing records
    - Add genuinely new records
    """
    refreshed_source_ids = set(refreshed_source_ids or [])
    fresh_ids = {n["id"] for n in fresh}
    existing_by_id = {n["id"]: n for n in existing}

    # An authoritative current-listing crawl can safely retire records that
    # disappeared. Generic pages are excluded because a partial parse there
    # should not close valid opportunities.
    for old in existing_by_id.values():
        if old.get("source_id") in refreshed_source_ids and old.get("id") not in fresh_ids:
            old["source_inactive"] = True
            old["inactive_reason"] = "removed from current agency listing"

    for n in fresh:
        nid = n["id"]
        if nid in existing_by_id:
            old = existing_by_id[nid]
            # Preserve manual overrides
            for field in ("status_override","noise_flagged","record_type_override","notice_subtype_override"):
                if old.get(field):
                    n[field] = old[field]
            # Update freshness fields
            # Legacy records have no known discovery date; never invent one.
            n["first_seen_at"] = old.get("first_seen_at")
            n["crawled_at"] = _now()
            n["source_inactive"] = False
            n["inactive_reason"] = ""
            existing_by_id[nid] = n
        else:
            previous = next((old for old in existing
                             if n.get("contract_number")
                             and old.get("source_id") == n.get("source_id")
                             and old.get("contract_number") == n.get("contract_number")), None)
            n["first_seen_at"] = previous.get("first_seen_at") if previous is not None else _now()
            n["source_inactive"] = False
            existing_by_id[nid] = n

    return list(existing_by_id.values())


# ── Crawl log ─────────────────────────────────────────────────────────────────

def _log_crawl(source_id, count, error=None, state=None, message=None):
    log_data = _load(CRAWL_LOG_F)
    # Find or create entry
    entry = next((e for e in log_data if e["source_id"] == source_id), None)
    if not entry:
        entry = {"source_id": source_id, "history": []}
        log_data.append(entry)

    crawled_at = _now()
    entry["last_crawl"]    = crawled_at
    entry["last_count"]    = count
    entry["last_error"]    = error
    entry["last_state"]    = state or ("error" if error else "ok")
    entry["last_message"]  = message
    entry["health"]        = "ok" if not error else "error"
    if not error:
        entry["last_successful_crawl"] = entry["last_crawl"]
    entry["history"]       = (entry.get("history",[]) + [{
        "at": crawled_at, "count": count, "error": error,
        "state": entry["last_state"], "message": message,
    }])[-30:]   # keep last 30 runs

    _save(CRAWL_LOG_F, log_data)


# ── Tier 3 SoS seed ───────────────────────────────────────────────────────────

def run_sos_seed():
    """Crawl SoS directory, discover municipal notice page URLs, save."""
    log.info("Running SoS directory seed...")
    sos_source = SOURCES_BY_ID.get("state-sos-directory")
    if not sos_source:
        log.error("SoS directory source not found in registry")
        return

    try:
        entities = parse_sos_directory(sos_source)
    except Exception as exc:
        _log_crawl(sos_source["id"], 0, str(exc))
        log.error(f"SoS seed failed: {exc}")
        return

    deduped = {entity["legal_notices_url"]: entity for entity in entities}
    validated = list(deduped.values())
    _save(SOS_ENT_F, validated)
    _log_crawl(sos_source["id"], len(validated), None)
    log.info(f"SoS seed: {len(validated)} validated entity notice pages")


# ── Tier 3 municipal crawl ────────────────────────────────────────────────────

def run_tier3_municipal():
    """
    Crawl all municipal legal notice pages discovered via SoS directory.
    Filter aggressively for transportation content.
    """
    entities = _load(SOS_ENT_F)
    if not entities:
        log.warning("No SoS entities found — run --seed-sos first")
        return []

    all_records = []
    for e in entities:
        url  = e.get("legal_notices_url","")
        name = e.get("entity_name","Unknown municipality")
        if not url: continue

        try:
            records = parse_municipal_from_sos(url, name)
        except Exception as exc:
            log.warning(f"  {name}: crawl failed: {exc}")
            continue
        if records:
            log.info(f"  {name}: {len(records)} transport-relevant notices")
            all_records.extend(records)

        import time; time.sleep(1.0)   # polite

    log.info(f"Tier 3 total: {len(all_records)} records from {len(entities)} municipalities")
    return all_records


# ── Main runner ───────────────────────────────────────────────────────────────

def run_crawl(sources_to_crawl):
    """Run crawls and return records plus authoritative sources refreshed."""
    all_fresh = []
    refreshed_source_ids = set()
    for source in sources_to_crawl:
        log.info(f"Crawling: {source['name']} ({source['id']})")
        if source.get("crawl_state") == "inaccessible":
            reason = source.get("access_reason", "This source cannot be crawled anonymously.")
            _log_crawl(source["id"], 0, state="inaccessible", message=reason)
            log.warning(f"  -> INACCESSIBLE: {reason}")
            continue
        try:
            records = crawl_source(source)
            crawl_error = "zero_records" if not records and not source.get("allow_empty") else None
            _log_crawl(source["id"], len(records), crawl_error)
            log.info(f"  → {len(records)} records")
            if crawl_error:
                log.warning(f"{source['id']} returned zero records; parser or source may have changed")
            elif source.get("parser") in AUTHORITATIVE_PARSERS and (
                records or source.get("empty_is_authoritative")
            ):
                refreshed_source_ids.add(source["id"])
            all_fresh.extend(records)
        except Exception as e:
            log.error(f"  → FAILED: {e}")
            _log_crawl(source["id"], 0, str(e))

    return all_fresh, refreshed_source_ids


def main():
    parser = argparse.ArgumentParser(description="NJ Transportation Bids — notice crawler")
    parser.add_argument("--weekly",  action="store_true", help="Include weekly sources")
    parser.add_argument("--tier",    type=int, choices=[1,2,3,4], help="Run only one tier")
    parser.add_argument("--source",  type=str, help="Run only one source by ID")
    parser.add_argument("--seed-sos",action="store_true", help="Refresh SoS entity directory")
    parser.add_argument("--dry-run", action="store_true", help="Print records, don't save")
    parser.add_argument(
        "--strict-health",
        action="store_true",
        help="Exit non-zero after saving when a critical source is unhealthy",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info(f"NJ Transportation Bids — Notice Crawler — {_today()}")
    log.info("=" * 60)

    # SoS seed mode
    if args.seed_sos:
        run_sos_seed()
        return

    # Determine which sources to crawl
    if args.source:
        src = SOURCES_BY_ID.get(args.source)
        if not src:
            log.error(f"Source not found: {args.source}")
            sys.exit(1)
        sources = [src]
    elif args.tier == 1:
        sources = TIER1_SOURCES
    elif args.tier == 2:
        sources = TIER2_SOURCES
    elif args.tier == 3:
        sources = TIER3_SOURCES
    elif args.tier == 4:
        sources = TIER4_SOURCES
    elif args.weekly:
        sources = NOTICE_SOURCES   # all sources
    else:
        sources = DAILY_SOURCES    # default: daily sources only

    # Filter out Tier 3 SoS-seed sources from main loop (handled separately)
    sources = [s for s in sources if s.get("parser") != "sos_directory"]

    log.info(f"Crawling {len(sources)} sources...")
    fresh, refreshed_source_ids = run_crawl(sources)

    # Tier 3 municipal if requested
    if args.tier == 3 or args.weekly:
        log.info("Running Tier 3 municipal crawl...")
        tier3 = run_tier3_municipal()
        fresh.extend(tier3)

    log.info(f"Raw records from crawl: {len(fresh)}")

    # Noise filter
    clean, noise = [], []
    for n in fresh:
        is_n, reason = _is_noise(n)
        if is_n:
            n["noise_flagged"] = True
            n["noise_reason"]  = reason
            noise.append(n)
        else:
            clean.append(n)
    log.info(f"After noise filter: {len(clean)} clean, {len(noise)} noise")

    # Enrich all
    enriched = [_enrich(n) for n in (clean + noise)]

    if args.dry_run:
        for n in enriched[:10]:
            print(json.dumps({k: n.get(k) for k in
                  ["title","status","notice_type","county","due_date_raw","source_name"]}, indent=2))
        log.info("Dry run — not saving")
        return

    # Load existing, merge, dedupe, save
    existing = _load(NOTICES_F)
    merged   = _merge(existing, enriched, refreshed_source_ids)
    deduped  = _dedupe(merged)

    # Re-evaluate every retained record, not only records fetched today. This
    # expires old deadlines and applies improved noise rules to historical
    # records that survive the merge.
    refreshed = []
    for notice in deduped:
        if not notice.get("status_override"):
            is_n, reason = _is_noise(notice)
            notice["noise_flagged"] = is_n
            notice["noise_reason"] = reason if is_n else ""
        refreshed.append(_enrich(notice))
    deduped = refreshed

    _save(NOTICES_F, deduped)

    health_summary = build_health_summary(NOTICE_SOURCES, _load(CRAWL_LOG_F), notices=deduped)
    _save(HEALTH_F, health_summary)

    # Summary
    active  = [n for n in deduped if n.get("status") in ("open", "upcoming") and not n.get("noise_flagged")]
    urgent  = [n for n in active if n.get("urgent")]
    log.info(f"Saved {len(deduped)} total notices")
    log.info(f"  Active: {len(active)}  |  Urgent (≤7 days): {len(urgent)}  |  Noise: {len(noise)}")
    log.info(
        "  Source health: %s healthy | %s warnings | %s errors | %s critical",
        health_summary["healthy_sources"],
        health_summary["warning_sources"],
        health_summary["error_sources"],
        health_summary["critical_failures"],
    )
    log.info("Done.")

    if args.strict_health and health_summary["critical_failures"]:
        log.error("Critical crawler source failures detected; see health_summary.json")
        sys.exit(2)


if __name__ == "__main__":
    main()
