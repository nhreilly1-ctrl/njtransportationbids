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
SOS_ENT_F    = DATA_DIR / "sos_entities.json"
OPP_F        = BASE / "data" / "opportunities.json"   # legacy file for merge

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
    3. Title similarity within same source — keep newer
    """
    seen_ids     = {}
    seen_contract = {}

    for n in sorted(notices, key=lambda x: x.get("crawled_at",""), reverse=True):
        nid = n.get("id","")
        src = n.get("source_id","")
        cno = (n.get("contract_number","") or "").strip().upper()
        title_key = f"{src}:{n.get('title','')[:80].lower()}"

        if nid in seen_ids:
            continue
        if cno and f"{src}:{cno}" in seen_contract:
            continue

        seen_ids[nid] = True
        if cno:
            seen_contract[f"{src}:{cno}"] = True

    # Rebuild list in original order, keeping first occurrence
    deduped = []
    seen_ids_final = set()
    seen_contract_final = set()
    for n in notices:
        nid = n.get("id","")
        src = n.get("source_id","")
        cno = (n.get("contract_number","") or "").strip().upper()
        ck  = f"{src}:{cno}" if cno else None

        if nid in seen_ids_final: continue
        if ck and ck in seen_contract_final: continue

        seen_ids_final.add(nid)
        if ck: seen_contract_final.add(ck)
        deduped.append(n)

    return deduped


# ── Enrichment ────────────────────────────────────────────────────────────────

def _enrich(n):
    """Compute status, days_until_due, preserve manual overrides."""
    # Respect admin overrides
    if n.get("status_override") in ("approved","noise","deleted"):
        n["status"] = n["status_override"]
        return n

    today = date.today()

    # Parse due date
    due = None
    raw = (n.get("due_date_raw") or "").strip()
    if raw and raw.lower() not in ("","not listed","—","-","unknown","n/a"):
        import re
        from datetime import datetime as dt
        fmts = ["%m/%d/%Y","%m/%d/%y","%B %d, %Y","%b %d, %Y",
                "%Y-%m-%d","%d-%b-%Y","%b. %d, %Y","%B %d %Y"]
        clean = re.sub(r"(open|closed|advertised|pending)[^\d]*","",raw,flags=re.I).strip()
        for fmt in fmts:
            try:
                due = dt.strptime(clean, fmt).date()
                break
            except ValueError:
                pass

    n["due_date_parsed"]  = due.isoformat() if due else None
    n["days_until_due"]   = (due - today).days if due else None

    # Status
    if n.get("noise_flagged") or n.get("status_override") == "noise":
        n["status"] = "noise"
    elif due and due < today:
        n["status"] = "expired"
    elif due:
        n["status"] = "open"
    else:
        n["status"] = "unknown_date"

    # Urgency flag
    n["urgent"] = (
        due is not None
        and n["status"] == "open"
        and (due - today).days <= 7
    )

    return n


# ── Noise filter (notices version) ────────────────────────────────────────────

NOTICE_NOISE_PHRASES = [
    "staff directory","vendor portal","sign in","how do i",
    "website sign","government departments","built to help",
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
]

def _is_noise(n):
    title = (n.get("title") or "").lower()
    excerpt = (n.get("notice_excerpt") or "").lower()
    text = title + " " + excerpt

    if len(title.split()) < 5:
        return True, "title too short"
    for p in NOTICE_NOISE_PHRASES:
        if p in text:
            return True, f"noise phrase: {p}"
    for k in OUT_OF_SCOPE_NOTICES:
        if k in title:
            return True, f"out of scope: {k}"
    return False, ""


# ── Merge with existing notices ───────────────────────────────────────────────

def _merge(existing, fresh):
    """
    Merge fresh crawl results into existing notices.
    - Preserve manual overrides (status_override, noise_flagged)
    - Update crawled_at and notice_excerpt for existing records
    - Add genuinely new records
    """
    existing_by_id = {n["id"]: n for n in existing}

    for n in fresh:
        nid = n["id"]
        if nid in existing_by_id:
            old = existing_by_id[nid]
            # Preserve manual overrides
            for field in ("status_override","noise_flagged","record_type_override","notice_subtype_override"):
                if old.get(field):
                    n[field] = old[field]
            # Update freshness fields
            n["crawled_at"] = _now()
            existing_by_id[nid] = n
        else:
            existing_by_id[nid] = n

    return list(existing_by_id.values())


# ── Crawl log ─────────────────────────────────────────────────────────────────

def _log_crawl(source_id, count, error=None):
    log_data = _load(CRAWL_LOG_F)
    # Find or create entry
    entry = next((e for e in log_data if e["source_id"] == source_id), None)
    if not entry:
        entry = {"source_id": source_id, "history": []}
        log_data.append(entry)

    entry["last_crawl"]    = _now()
    entry["last_count"]    = count
    entry["last_error"]    = error
    entry["health"]        = "ok" if not error else "error"
    entry["history"]       = (entry.get("history",[]) + [{
        "at": _now(), "count": count, "error": error
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

    entities = parse_sos_directory(sos_source)
    existing  = _load(SOS_ENT_F)
    seen_urls = {e["legal_notices_url"] for e in existing}

    new_count = 0
    for e in entities:
        if e["legal_notices_url"] not in seen_urls:
            existing.append(e)
            seen_urls.add(e["legal_notices_url"])
            new_count += 1

    _save(SOS_ENT_F, existing)
    log.info(f"SoS seed: {new_count} new entities discovered. Total: {len(existing)}")


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

        records = parse_municipal_from_sos(url, name)
        if records:
            log.info(f"  {name}: {len(records)} transport-relevant notices")
            all_records.extend(records)

        import time; time.sleep(1.0)   # polite

    log.info(f"Tier 3 total: {len(all_records)} records from {len(entities)} municipalities")
    return all_records


# ── Main runner ───────────────────────────────────────────────────────────────

def run_crawl(sources_to_crawl):
    """Run crawl for a list of source dicts. Return all records."""
    all_fresh = []
    for source in sources_to_crawl:
        log.info(f"Crawling: {source['name']} ({source['id']})")
        try:
            records = crawl_source(source)
            _log_crawl(source["id"], len(records))
            log.info(f"  → {len(records)} records")
            all_fresh.extend(records)
        except Exception as e:
            log.error(f"  → FAILED: {e}")
            _log_crawl(source["id"], 0, str(e))

    return all_fresh


def main():
    parser = argparse.ArgumentParser(description="NJ Transportation Bids — notice crawler")
    parser.add_argument("--weekly",  action="store_true", help="Include weekly sources")
    parser.add_argument("--tier",    type=int, choices=[1,2,3,4], help="Run only one tier")
    parser.add_argument("--source",  type=str, help="Run only one source by ID")
    parser.add_argument("--seed-sos",action="store_true", help="Refresh SoS entity directory")
    parser.add_argument("--dry-run", action="store_true", help="Print records, don't save")
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
    fresh = run_crawl(sources)

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
    merged   = _merge(existing, enriched)
    deduped  = _dedupe(merged)

    _save(NOTICES_F, deduped)

    # Summary
    active  = [n for n in deduped if n.get("status") in ("open","unknown_date") and not n.get("noise_flagged")]
    urgent  = [n for n in active if n.get("urgent")]
    log.info(f"Saved {len(deduped)} total notices")
    log.info(f"  Active: {len(active)}  |  Urgent (≤7 days): {len(urgent)}  |  Noise: {len(noise)}")
    log.info("Done.")


if __name__ == "__main__":
    main()
