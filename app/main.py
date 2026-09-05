import csv
import functools
import hashlib
import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from xml.sax.saxutils import escape

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for

from app.core.deadlines import (
    EASTERN,
    eastern_today,
    deadline_date,
    deadline_days_remaining,
    deadline_is_past,
    format_eastern_timestamp,
    normalize_deadline,
    reconcile_authoritative_open_deadline,
)
from app.core.corridors import enrich_location, location_display, map_url
from app.core.geography import NJ_COUNTIES, enrich_geography
from crawlers.notice_sources import NOTICE_SOURCES
from crawlers.source_health import build_health_summary
from app.core.bid_readiness import readiness_for
from app.core.relatedness import rank_related
from app.core.scanning import matches_search
from app.resource_catalog import RESOURCE_SECTIONS, resource_count


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
logger = logging.getLogger(__name__)

from app.notice_routes import notice_bp
app.register_blueprint(notice_bp)

from app.network_routes import network_bp
app.register_blueprint(network_bp)

@app.context_processor
def inject_globals():
    noindex_prefixes = ("/admin", "/network", "/export/")
    return {
        "today_date": date.today().isoformat(),
        "site_url": SITE_URL,
        "canonical_url": f"{SITE_URL}{request.path}",
        "robots_meta": "noindex, nofollow" if request.path.startswith(noindex_prefixes) else "index, follow",
    }

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(BASE, "data") if os.path.isdir(os.path.join(BASE, "data")) else os.path.join(BASE, "data_store")
OPP_F = os.path.join(DATA, "opportunities.json")
SRC_F = os.path.join(DATA, "sources.json")
NOTICE_F = os.path.join(BASE, "data", "notices", "notices.json")
CRAWL_LOG_F = os.path.join(BASE, "data", "notices", "crawl_log.json")
HEALTH_F = os.path.join(BASE, "data", "notices", "health_summary.json")
SITE_URL = os.environ.get("SITE_URL", "https://www.njtransportationbids.com").rstrip("/")

ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
_admin_password = os.environ.get("ADMIN_PASSWORD")
ADMIN_HASH = os.environ.get("ADMIN_PASSWORD_HASH") or (
    hashlib.sha256(_admin_password.encode()).hexdigest()
    if _admin_password
    else hashlib.sha256(b"changeme").hexdigest()
)

SOURCE_TYPE_MAP = {
    "njdot construction": "construction",
    "notice to contractors": "construction",
    "port authority construction": "construction",
    "drjtbc notice to contractors": "construction",
    "njdot professional services": "professional_services",
    "njdot procurement notices": "professional_services",
    "port authority professional": "professional_services",
    "drjtbc current": "professional_services",
    "nj department of state legal": "public_notice",
    "nj department of state public": "public_notice",
    "south jersey transportation authority legal": "public_notice",
    "nj treasury legal": "public_notice",
    "city of trenton legal": "public_notice",
}

SOURCE_ID_FALLBACK_TYPES = {
    "state-njdot-construction": "construction",
    "state-njdot-profserv": "professional_services",
    "state-drjtbc-construction": "construction",
    "state-drjtbc-profserv": "professional_services",
    "state-njta": "construction",
}

TITLE_TYPE_RULES = [
    (
        "public_notice",
        [
            "notice to all",
            "notice to contractors",
            "legal notice",
            "notice of intent",
            "legal ad",
            "public notice",
            "prequalif",
            "pre-qualif",
            "pre qualif",
            "2025 eeo",
            "2026 eeo",
        ],
    ),
    (
        "professional_services",
        [
            "rfp ",
            "rfq ",
            "rfp-",
            "rfq-",
            "request for proposal",
            "request for qualif",
            "professional services",
            "engineering services",
            "design services",
            "inspection services",
            "planning services",
            "construction inspection",
            "structural evaluation",
            "underwater inspection",
            "consulting",
            "consultant",
            "feasibility",
            "alternatives analysis",
            "program management",
            "cpmc",
            "order for professional",
            "op no.",
            "ops no.",
            "tp-",
            "tp -",
        ],
    ),
    (
        "construction",
        [
            "bid no.",
            "bid no ",
            "bid number",
            "ifb ",
            "ifb no.",
            "invitation for bids",
            "contract no.",
            "contract no ",
            "contract number",
            "roadway improvement",
            "road improvement",
            "road resurfacing",
            "pavement",
            "milling",
            "resurfacing",
            "overlay",
            "bridge replacement",
            "bridge rehabilitation",
            "bridge repair",
            "drainage improvement",
            "drainage repair",
            "intersection improvement",
            "signal",
            "guide rail",
            "guardrail",
            "culvert",
            "maintenance contract",
            "snow removal",
            "construction",
        ],
    ),
]

PUBLIC_NOTICE_CONSTRUCTION_SIGNALS = [
    "construction",
    "roadway",
    "bridge",
    "pavement",
    "drainage",
    "intersection",
    "culvert",
    "resurfacing",
    "guide rail",
    "maintenance",
    "notice to contractors",
    "bid opening",
    "contract award",
    "t200.",
    "t100.",
    "p200.",
    "p500.",
]

PUBLIC_NOTICE_PROFSERV_SIGNALS = [
    "rfp",
    "rfq",
    "professional services",
    "engineering",
    "design",
    "inspection",
    "planning",
    "consultant",
    "program management",
    "cpmc",
    "feasibility",
    "alternatives analysis",
    "tp-",
    "ops no.",
    "op no.",
]

NOISE_PHRASES = [
    "sign in",
    "staff directory",
    "vendor portal",
    "how do i",
    "search home",
    "website sign",
    "government departments",
    "built to help vendors",
    "in order to maintain",
    "contract documents or any",
    "contract documents should",
    "contract awards",
    "notice to all",
    "procurement calendar",
    "professional services upcoming",
    "professional services /",
    "rfbs (request for bids) awarded",
    "rfbs (request for bids) upcoming",
    "rfps (request for proposals) fair",
    "rfpq",
    "bidder's application",
    "results of bid/rfp",
    "bids and tenders",
    "camden business improvement",
    "comprehensive bridge replacement and improvement plan",
    "government records - bridge",
    "construction and materials",
    "mobility and systems",
    "vendor/contractor assistance",
    "alternative project delivery",
]

OUT_OF_SCOPE = [
    "harley",
    "davidson",
    "motorcycle",
    "cannabis",
    "housing rehabilitation",
    "septic",
    "arboriculture",
    "arborist",
    "eeoc",
    "affordable housing",
    "small cities",
    "exhibition design",
    "black heritage",
    "historic marker",
    "landscape maintenance",
    "ev charging",
    "electric vehicle charging",
    "rfq #25-arch",
    "rfq #25-njbac",
    "rfq #cc120",
]

SOURCE_RULES = {
    "state-njdot-construction": {"score": 5.0, "mode": "trusted", "label": "Trusted"},
    "state-njdot-profserv": {"score": 5.0, "mode": "trusted", "label": "Trusted"},
    "state-drjtbc-construction": {"score": 5.0, "mode": "trusted", "label": "Trusted"},
    "state-drjtbc-profserv": {"score": 5.0, "mode": "trusted", "label": "Trusted"},
    "state-njta": {"score": 4.5, "mode": "trusted", "label": "Trusted"},
    "state-njtransit": {"score": 4.5, "mode": "trusted", "label": "Trusted"},
    "state-panynj-construction": {"score": 4.5, "mode": "trusted", "label": "Trusted"},
    "state-panynj-profserv": {"score": 4.5, "mode": "trusted", "label": "Trusted"},
    "county-camden": {"score": 4.0, "mode": "ai_review", "label": "AI review"},
    "county-burlington": {"score": 4.0, "mode": "ai_review", "label": "AI review"},
    "municipal-jersey-city": {"score": 4.0, "mode": "ai_review", "label": "AI review"},
    "municipal-hoboken": {"score": 4.0, "mode": "ai_review", "label": "AI review"},
    "county-bergen": {"score": 3.5, "mode": "ai_review", "label": "AI review"},
    "county-essex": {"score": 3.5, "mode": "manual_review", "label": "Manual review"},
    "municipal-paterson": {"score": 3.5, "mode": "manual_review", "label": "Manual review"},
    "municipal-elizabeth": {"score": 3.5, "mode": "manual_review", "label": "Manual review"},
    "county-cape-may": {"score": 3.5, "mode": "manual_review", "label": "Manual review"},
    "county-hudson": {"score": 3.5, "mode": "manual_review", "label": "Manual review"},
    "municipal-camden": {"score": 3.5, "mode": "manual_review", "label": "Manual review"},
    "county-cumberland": {"score": 3.0, "mode": "manual_review", "label": "Manual review"},
    "county-gloucester": {"score": 3.0, "mode": "manual_review", "label": "Manual review"},
    "county-hunterdon": {"score": 3.0, "mode": "manual_review", "label": "Manual review"},
    "municipal-newark": {"score": 2.0, "mode": "metadata_only", "label": "Metadata only"},
    "county-atlantic": {"score": 1.0, "mode": "disabled", "label": "Disabled"},
    "county-mercer": {"score": 1.0, "mode": "disabled", "label": "Disabled"},
    "municipal-trenton": {"score": 1.0, "mode": "disabled", "label": "Disabled"},
}

DEFAULT_SOURCE_RULE = {"score": 2.5, "mode": "manual_review", "label": "Manual review"}


def _check_pw(password: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == ADMIN_HASH


def admin_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


def use_db_backend() -> bool:
    backend = os.environ.get("DATA_BACKEND", "file").strip().lower()
    return backend != "file" and bool(os.environ.get("DATABASE_URL"))


def get_conn():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(db_url)


def is_db_available() -> bool:
    if not use_db_backend():
        return False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        logger.exception("Database connectivity check failed.")
        return False


def init_db_schema() -> None:
    if not use_db_backend():
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE opportunity_leads ADD COLUMN IF NOT EXISTS status_override TEXT;")
                cur.execute("ALTER TABLE opportunity_leads ADD COLUMN IF NOT EXISTS noise_flagged BOOLEAN DEFAULT FALSE;")
                cur.execute("ALTER TABLE opportunity_leads ADD COLUMN IF NOT EXISTS noise_reason TEXT;")
                cur.execute("ALTER TABLE opportunity_leads ADD COLUMN IF NOT EXISTS record_type_override TEXT;")
                cur.execute("ALTER TABLE opportunity_leads ADD COLUMN IF NOT EXISTS notice_subtype_override TEXT;")
            conn.commit()
    except Exception:
        pass


def load_json_file(path: str) -> list[dict]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_json_file(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2, default=str)


def source_tier(source_id: str | None, entity_type: str | None) -> str:
    source_id = (source_id or "").lower()
    entity = (entity_type or "").lower()
    if source_id.startswith("state-") or "state" in entity or "authority" in entity or "transit" in entity:
        return "state"
    if source_id.startswith("county-") or "county" in entity:
        return "county"
    return "municipal"


def source_rule_for(source_id: str | None) -> dict:
    return dict(SOURCE_RULES.get((source_id or "").lower(), DEFAULT_SOURCE_RULE))


def load_opps_from_db() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    l.lead_id::text AS id,
                    l.source_id,
                    l.title,
                    COALESCE(NULLIF(rs.source_name, ''), NULLIF(l.agency, ''), l.source_id) AS source_name,
                    NULLIF(l.agency, '') AS agency,
                    NULLIF(l.county, '') AS county,
                    l.due_date AS due_date_raw,
                    l.source_url AS official_url,
                    NULLIF(l.access_type, '') AS access_type,
                    NULLIF(l.platform_name, '') AS platform,
                    NULLIF(l.next_step, '') AS next_step,
                    NULLIF(l.docs_path_note, '') AS docs_path_note,
                    NULLIF(l.addenda_note, '') AS addenda_note,
                    COALESCE(l.status_override, '') AS status_override,
                    COALESCE(l.noise_flagged, FALSE) AS noise_flagged,
                    COALESCE(l.noise_reason, '') AS noise_reason,
                    COALESCE(l.admin_notes, '') AS admin_notes,
                    COALESCE(l.record_type_override, '') AS record_type_override,
                    COALESCE(l.notice_subtype_override, '') AS notice_subtype_override,
                    COALESCE(l.status, '') AS db_status,
                    COALESCE(l.raw_text, '') AS raw_text,
                    l.created_at
                FROM opportunity_leads l
                LEFT JOIN registry_sources rs ON rs.source_id = l.source_id
                WHERE COALESCE(l.status, '') != 'Rejected'
                ORDER BY l.created_at DESC NULLS LAST, l.title
                """
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def load_sources_from_db() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    source_id,
                    source_name,
                    entity_type,
                    county,
                    source_url,
                    last_crawl_at,
                    last_crawl_status,
                    last_leads_found
                FROM registry_sources
                ORDER BY source_name
                """
            )
            rows = cur.fetchall()
    sources = []
    for row in rows:
        item = dict(row)
        sources.append(
            {
                "id": item["source_id"],
                "name": item["source_name"],
                "tier": source_tier(item["source_id"], item.get("entity_type")),
                "source_rule": source_rule_for(item["source_id"])["mode"],
                "rule_label": source_rule_for(item["source_id"])["label"],
                "crawlability_score": source_rule_for(item["source_id"])["score"],
                "county": item.get("county"),
                "url": item.get("source_url"),
                "last_crawl": item["last_crawl_at"].isoformat(sep=" ", timespec="minutes") if item.get("last_crawl_at") else None,
                "last_status": item.get("last_crawl_status"),
                "last_leads_found": item.get("last_leads_found") or 0,
            }
        )
    return sources


def load_opps() -> list[dict]:
    if use_db_backend():
        try:
            return load_opps_from_db()
        except Exception:
            logger.exception("Falling back to file-backed opportunities data.")
    return load_json_file(OPP_F)


def save_opps(opps: list[dict]) -> None:
    if not use_db_backend():
        save_json_file(OPP_F, opps)


def load_sources() -> list[dict]:
    if use_db_backend():
        try:
            return load_sources_from_db()
        except Exception:
            logger.exception("Falling back to file-backed sources data.")
    return load_json_file(SRC_F)


def load_public_opps() -> list[dict]:
    """Return the canonical official-notice feed for public pages.

    The GitHub Actions crawler writes notices.json, while the older database
    importer writes opportunity_leads. Public pages must not silently show a
    different dataset from the one the crawler just refreshed.
    """
    notices = load_json_file(NOTICE_F)
    if not notices:
        return load_opps()

    records = []
    for notice in notices:
        record = dict(notice)
        record["_canonical_notice"] = True
        record["id"] = str(record.get("id", ""))
        record["title"] = record.get("title") or "Untitled notice"
        record["source_name"] = record.get("source_name") or record.get("source_id", "Unknown source")
        record["official_url"] = record.get("official_url") or record.get("source_url")
        record["due_date_raw"] = record.get("due_date_raw") or ""
        records.append(record)
    return records


def load_source_health_summary() -> dict:
    """Evaluate current source status from the activity log, with snapshot fallback."""
    try:
        with open(CRAWL_LOG_F, encoding="utf-8") as handle:
            return build_health_summary(NOTICE_SOURCES, json.load(handle))
    except (OSError, ValueError, TypeError):
        try:
            with open(HEALTH_F, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError, TypeError):
            return build_health_summary(NOTICE_SOURCES, [])


def load_public_sources() -> list[dict]:
    """Return every monitored public source, including sources with zero records."""
    summary = load_source_health_summary()
    health_by_id = {item.get("source_id"): item for item in summary.get("sources", [])}
    sources = []
    for configured in NOTICE_SOURCES:
        source_id = configured["id"]
        health = health_by_id.get(source_id, {})
        severity = health.get("severity", "warning")
        sources.append(
            {
                "id": source_id,
                "name": configured["name"],
                "tier": configured.get("source_tier") or "other",
                "county": configured.get("county"),
                "url": configured.get("url"),
                "frequency": configured.get("crawl_freq", "weekly"),
                "critical": bool(configured.get("critical")),
                "access_state": configured.get("crawl_state", "accessible"),
                "access_reason": configured.get("access_reason"),
                "last_crawl": health.get("last_crawl"),
                "last_crawl_display": format_eastern_timestamp(health.get("last_crawl")),
                "last_count": health.get("last_count"),
                "status": health.get("status", "never_run"),
                "severity": severity,
                "health": "good" if severity == "ok" else "warn" if severity == "warning" else "bad",
                "health_message": health.get("message", "No source status is available."),
            }
        )
    return sorted(sources, key=lambda item: (item["tier"], item["name"].lower()))


def classify_record(opp: dict) -> tuple[str, str | None]:
    manual_type = (opp.get("record_type_override") or "").strip()
    manual_subtype = (opp.get("notice_subtype_override") or "").strip() or None
    if manual_type:
        return manual_type, manual_subtype

    title = (opp.get("title") or "").lower()
    src_name = (opp.get("source_name") or "").lower()
    source_id = (opp.get("source_id") or "").lower()

    src_type = None
    for key, value in SOURCE_TYPE_MAP.items():
        if key in src_name or key in source_id:
            src_type = value
            break

    title_type = None
    for record_type, keywords in TITLE_TYPE_RULES:
        if any(keyword in title for keyword in keywords):
            title_type = record_type
            break

    record_type = title_type or src_type or SOURCE_ID_FALLBACK_TYPES.get(source_id) or "uncategorized"
    notice_subtype = None
    if record_type == "public_notice":
        if any(keyword in title for keyword in PUBLIC_NOTICE_CONSTRUCTION_SIGNALS):
            notice_subtype = "construction"
        elif any(keyword in title for keyword in PUBLIC_NOTICE_PROFSERV_SIGNALS):
            notice_subtype = "professional_services"

    return record_type, notice_subtype


def update_leads(ids: list[str], action: str, record_type: str | None = None, notice_subtype: str | None = None) -> int:
    if not ids:
        return 0

    if not use_db_backend():
        opps = load_opps()
        changed = 0
        id_set = set(ids)
        for opp in opps:
            if opp.get("id") not in id_set:
                continue
            if action == "delete":
                opp["status_override"] = "deleted"
                opp["noise_flagged"] = False
            elif action == "noise":
                opp["status_override"] = "noise"
                opp["noise_flagged"] = True
            elif action == "approve":
                opp["status_override"] = "approved"
                opp["noise_flagged"] = False
                opp["noise_reason"] = ""
            elif action == "restore":
                opp["status_override"] = ""
                opp["noise_flagged"] = False
                opp["noise_reason"] = ""
            elif action == "set_type" and record_type:
                opp["record_type_override"] = record_type
                opp["notice_subtype_override"] = notice_subtype or ""
            changed += 1
        save_opps(opps)
        return changed

    with get_conn() as conn:
        with conn.cursor() as cur:
            if action == "set_type" and record_type:
                cur.execute(
                    """
                    UPDATE opportunity_leads
                    SET
                        record_type_override = %s,
                        notice_subtype_override = %s
                    WHERE lead_id = ANY(%s)
                    """,
                    (record_type, notice_subtype, ids),
                )
            else:
                mapping = {
                    "delete": ("deleted", False, None),
                    "noise": ("noise", True, None),
                    "approve": ("approved", False, ""),
                    "restore": ("", False, ""),
                }
                status_override, noise_flagged, noise_reason = mapping[action]
                cur.execute(
                    """
                    UPDATE opportunity_leads
                    SET
                        status_override = %s,
                        noise_flagged = %s,
                        noise_reason = CASE WHEN %s IS NULL THEN noise_reason ELSE %s END
                    WHERE lead_id = ANY(%s)
                    """,
                    (status_override, noise_flagged, noise_reason, noise_reason, ids),
                )
            changed = cur.rowcount
        conn.commit()
    return changed


def patch_lead(opp_id: str, patch: dict) -> bool:
    allowed = {
        "title": "title",
        "due_date_raw": "due_date",
        "county": "county",
        "official_url": "source_url",
        "access_type": "access_type",
        "platform": "platform_name",
        "next_step": "next_step",
        "docs_path_note": "docs_path_note",
        "addenda_note": "addenda_note",
        "status_override": "status_override",
        "noise_flagged": "noise_flagged",
        "noise_reason": "noise_reason",
        "record_type_override": "record_type_override",
        "notice_subtype_override": "notice_subtype_override",
    }

    if not use_db_backend():
        opps = load_opps()
        record = next((opp for opp in opps if opp.get("id") == opp_id), None)
        if not record:
            return False
        for key, value in patch.items():
            if key in allowed:
                record[key] = value
        save_opps(opps)
        return True

    assignments = []
    values = []
    for key, column in allowed.items():
        if key in patch:
            assignments.append(f"{column} = %s")
            values.append(patch[key])

    if not assignments:
        return False

    values.append(opp_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE opportunity_leads SET {', '.join(assignments)} WHERE lead_id = %s",
                values,
            )
            changed = cur.rowcount
        conn.commit()
    return bool(changed)


def clear_noise_flags() -> int:
    if not use_db_backend():
        opps = load_opps()
        count = 0
        for opp in opps:
            if opp.get("status_override"):
                continue
            if opp.get("noise_flagged") or opp.get("noise_reason"):
                opp["noise_flagged"] = False
                opp["noise_reason"] = ""
                count += 1
        save_opps(opps)
        return count

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE opportunity_leads
                SET noise_flagged = FALSE, noise_reason = ''
                WHERE COALESCE(status_override, '') = ''
                """
            )
            count = cur.rowcount
        conn.commit()
    return count


def noise_score(opp: dict) -> tuple[bool, str]:
    title = (opp.get("title") or "").lower()
    if len(title.split()) < 6:
        return True, "title too short"
    for phrase in NOISE_PHRASES:
        if phrase in title:
            return True, f"nav/boilerplate: {phrase}"
    for keyword in OUT_OF_SCOPE:
        if keyword in title:
            return True, f"out of scope: {keyword}"
    return False, ""


def parse_due(raw: str | None) -> date | None:
    normalized = normalize_deadline({"due_date_raw": raw or ""})
    return deadline_date(normalized)


def enrich(opp: dict) -> dict:
    record = dict(opp)
    enrich_geography(record)
    enrich_location(record)
    # Rule 2 of docs/TIME_AND_TOOLS.md: the most specific location evidence
    # leads. A notice naming the NJ Turnpike must not read "County not stated"
    # just because no county was extracted; the scope label still follows when
    # it carries meaning (a county list, Bi-state, Statewide, or a region).
    evidenced = location_display(record)
    county_label = record.get("county_display") or ""
    if evidenced and county_label and county_label != "County not stated in notice":
        evidenced = f"{evidenced} · {county_label}"
    record["location_display"] = evidenced
    record["map_url"] = map_url(record)
    normalize_deadline(record)
    deadline_conflict = reconcile_authoritative_open_deadline(record)
    due = deadline_date(record)
    crawled_at = str(record.get("crawled_at") or record.get("created_at") or "")
    record["last_verified_date"] = crawled_at[:10] if len(crawled_at) >= 10 else None

    if record.get("_canonical_notice"):
        record["source_rule"] = "trusted" if record.get("source_tier") == "state" else "ai_review"
        record["source_rule_label"] = "Official source monitor"
        record["crawlability_score"] = 5.0 if record.get("source_tier") == "state" else 3.5
        if record.get("status_override") == "deleted":
            record["status"] = "deleted"
        elif record.get("noise_flagged"):
            record["status"] = "noise"
        elif record.get("source_inactive"):
            record["status"] = "expired"
        elif record.get("geography_review_required") or record.get("parser_review_required"):
            record["status"] = "review_required"
        elif record.get("is_planned") or record.get("status") == "upcoming":
            record["status"] = "upcoming"
        elif deadline_conflict:
            record["status"] = "open"
        elif deadline_is_past(record):
            record["status"] = "expired"
        elif due or record.get("status") == "open" or record.get("source_status") in ("open", "advertised", "current"):
            record["status"] = "open"
        else:
            record["status"] = "unknown_date"
        record["record_type"] = record.get("notice_type") or "uncategorized"
        record["notice_subtype"] = record.get("notice_subtype")
        return record

    rule = source_rule_for(record.get("source_id"))
    record["source_rule"] = rule["mode"]
    record["source_rule_label"] = rule["label"]
    record["crawlability_score"] = rule["score"]

    manual = record.get("status_override")
    today = date.today()
    if manual == "deleted":
        record["status"] = "deleted"
    elif manual == "noise":
        record["status"] = "noise"
    elif record["source_rule"] == "disabled":
        record["status"] = "disabled"
    else:
        is_noise, reason = noise_score(record)
        if record.get("noise_flagged"):
            record["status"] = "noise"
            record["noise_reason"] = record.get("noise_reason") or "manually flagged"
        elif is_noise and manual != "approved":
            record["status"] = "noise"
            record["noise_reason"] = reason
        elif deadline_conflict:
            record["status"] = "open"
        elif deadline_is_past(record):
            record["status"] = "expired"
        elif manual == "approved":
            record["status"] = "open"
        elif due:
            if record["source_rule"] == "trusted":
                record["status"] = "open"
            elif record["source_rule"] == "ai_review":
                record["status"] = "ai_review"
            else:
                record["status"] = "review_required"
        else:
            record["status"] = "review_required"

    record_type, notice_subtype = classify_record(record)
    record["record_type"] = record_type
    record["notice_subtype"] = notice_subtype
    return record


SEO_GEOGRAPHY_PROVENANCE = {"NOTICE_TEXT", "SOURCE_RECORD_FIELD"}
SEO_DP_RE = re.compile(r"\bDP\s*(?:No\.?|Number|#)?\s*:?\s*([A-Z0-9-]+)\b", re.IGNORECASE)
SEO_MUNICIPALITY_RE = re.compile(
    r"\b(?:Township|City|Borough|Town|Village)\s+of\s+([^,;]+)",
    re.IGNORECASE,
)


def _clean_seo_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" ,.;:-")


def _truncate_seo_text(value: str, limit: int) -> str:
    value = _clean_seo_text(value)
    if len(value) <= limit:
        return value
    shortened = value[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    words = shortened.split()
    if words and words[-1].lower() in {"and", "for", "in", "of", "on", "or", "the", "with"}:
        shortened = " ".join(words[:-1])
    return shortened or value[:limit].rstrip(" ,.;:-")


def _seo_counties(record: dict) -> list[str]:
    if record.get("geography_provenance") not in SEO_GEOGRAPHY_PROVENANCE:
        return []
    return [county for county in record.get("counties", []) if county in NJ_COUNTIES]


def _strip_unsupported_counties(value: str, supported: list[str]) -> str:
    cleaned = value
    for county in NJ_COUNTIES:
        if county in supported:
            continue
        patterns = (
            rf"\bCounty\s+of\s+{re.escape(county)}\b",
            rf"\b{re.escape(county)}\s+County\b",
            rf"\b{re.escape(county)}\b",
        )
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return _clean_seo_text(re.sub(r"\s*[,;|]\s*(?=[,;|]|$)", " ", cleaned))


def _seo_agency_label(record: dict, supported_counties: list[str]) -> str:
    source_id = _clean_seo_text(record.get("source_id")).lower()
    source_name = _clean_seo_text(record.get("source_name"))
    agency_aliases = (
        (("state-njdot", "njdot"), "NJDOT"),
        (("state-njta", "turnpike-authority"), "NJTA"),
        (("nj-transit",), "NJ TRANSIT"),
        (("panynj", "port-authority"), "Port Authority NY/NJ"),
        (("drjtbc",), "DRJTBC"),
        (("sjta",), "SJTA"),
    )
    haystack = f"{source_id} {source_name.lower()}"
    for needles, label in agency_aliases:
        if any(needle in haystack for needle in needles):
            return label

    safe_name = _strip_unsupported_counties(source_name, supported_counties)
    if safe_name.lower() in {"", "bids", "procurement", "procurements", "purchasing"}:
        return ""
    return _truncate_seo_text(safe_name, 34)


def _seo_location(record: dict, supported_counties: list[str]) -> str:
    raw_title = _clean_seo_text(record.get("title"))
    municipality_match = SEO_MUNICIPALITY_RE.search(raw_title)
    municipality = _truncate_seo_text(municipality_match.group(1), 28) if municipality_match else ""
    if len(supported_counties) == 1:
        county_label = f"{supported_counties[0]} County"
    elif len(supported_counties) == 2:
        county_label = f"{supported_counties[0]} and {supported_counties[1]} Counties"
    elif supported_counties:
        county_label = f"{supported_counties[0]}, {supported_counties[1]} and other NJ counties"
    else:
        county_label = ""
    return ", ".join(part for part in (municipality, county_label) if part)


def build_opportunity_seo(record: dict) -> dict[str, str]:
    """Compose evidence-safe search metadata without re-deriving county geography."""
    supported_counties = _seo_counties(record)
    raw_title = _clean_seo_text(record.get("title") or "New Jersey transportation opportunity")
    project_title = re.split(
        r",?\s*(?=(?:Contract\s*(?:No\.?|Number|#)|Federal Project|UPC\s+No\.?|PE\s+No\.?|CE\s+No\.?|DP\s+(?:No\.?|Number|#)))",
        raw_title,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    project_title = _strip_unsupported_counties(project_title, supported_counties)
    project_title = project_title or "New Jersey transportation opportunity"

    contract_number = _clean_seo_text(record.get("contract_number"))
    contract_label = f"Contract {contract_number}" if contract_number else ""
    dp_match = SEO_DP_RE.search(raw_title)
    dp_label = f"DP {dp_match.group(1)}" if dp_match else ""
    if dp_label and contract_number and dp_match.group(1).lower() in contract_number.lower():
        dp_label = ""

    location = _seo_location(record, supported_counties)
    agency = _seo_agency_label(record, supported_counties)
    title_location = location
    if supported_counties and ", " in location:
        title_location = location.split(", ", 1)[1]
    title_tail = [part for part in (contract_label, dp_label, title_location, agency) if part]
    reserved = len(" | ".join(title_tail)) + (3 if title_tail else 0)
    title_project = _truncate_seo_text(project_title, max(34, 100 - reserved))
    seo_title = " | ".join([title_project, *title_tail])

    type_label = {
        "construction": "construction bid",
        "professional_services": "engineering and professional services opportunity",
        "public_notice": "transportation procurement notice",
    }.get(record.get("record_type"), "transportation procurement opportunity")
    description_prefix = f"{agency or 'New Jersey'} {type_label}: "
    detail_parts = []
    references = "; ".join(part for part in (contract_label, dp_label) if part)
    if references:
        detail_parts.append(references)
    if location:
        detail_parts.append(location)
    if record.get("due_date_raw") and record.get("deadline_display"):
        deadline_label = "Expected" if record.get("status") == "upcoming" else "Due"
        detail_parts.append(f"{deadline_label} {record['deadline_display']}")
    description_tail = ". ".join(detail_parts)
    if description_tail:
        description_tail += "."
    project_limit = max(36, 170 - len(description_prefix) - len(description_tail) - 1)
    seo_description = f"{description_prefix}{_truncate_seo_text(project_title, project_limit)}."
    if description_tail:
        seo_description += f" {description_tail}"

    return {
        "title": seo_title,
        "description": seo_description,
    }


def sort_opps(opps: list[dict]) -> list[dict]:
    return sorted(
        opps,
        key=lambda opp: (
            1 if not opp.get("due_date_parsed") or opp.get("deadline_conflict") else 0,
            "9999-12-31" if opp.get("deadline_conflict") else opp.get("due_date_parsed") or "9999-12-31",
            opp.get("deadline_at") or "9999-12-31T23:59:59Z",
            (opp.get("title") or "").lower(),
        ),
    )


def group_opportunity_scan(opps: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Group an already deadline-sorted public result set for market scanning."""
    today = eastern_today()
    cutoff = today + timedelta(days=7)
    soon, this_month, upcoming, nodate, closed = [], [], [], [], []
    for opp in opps:
        if opp.get("status") in ("expired", "noise"):
            closed.append(opp)
            continue
        if opp.get("status") == "upcoming":
            upcoming.append(opp)
            continue
        if opp.get("deadline_conflict") or deadline_is_past(opp):
            nodate.append(opp)
            continue
        if opp.get("due_date_parsed"):
            due = date.fromisoformat(opp["due_date_parsed"])
            if due <= cutoff:
                soon.append(opp)
            elif due.year == today.year and due.month == today.month:
                this_month.append(opp)
            else:
                upcoming.append(opp)
        else:
            nodate.append(opp)
    closed.sort(
        key=lambda opp: (
            bool(opp.get("due_date_parsed")),
            opp.get("due_date_parsed") or "",
            (opp.get("title") or "").lower(),
        ),
        reverse=True,
    )
    return soon, this_month, upcoming, nodate, closed


@app.route("/health")
def health():
    db_configured = bool(os.environ.get("DATABASE_URL"))
    db_enabled = use_db_backend()
    db_available = is_db_available() if db_enabled else False
    return jsonify(
        {
            "ok": True,
            "data_backend": "database" if db_enabled else "file",
            "database": {
                "configured": db_configured,
                "enabled": db_enabled,
                "available": db_available,
            },
        }
    )


@app.route("/robots.txt")
def robots_txt():
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin",
            "Disallow: /export/",
            "Disallow: /network",
            "Disallow: /*?",
            f"Sitemap: {SITE_URL}/sitemap.xml",
            "",
        ]
    )
    return Response(body, mimetype="text/plain")


@app.route("/google0a60cf7052b4fd95.html")
def google_site_verification():
    return Response(
        "google-site-verification: google0a60cf7052b4fd95.html\n",
        mimetype="text/html",
    )


@app.route("/sitemap.xml")
def sitemap_xml():
    paths = [
        "/",
        "/bids/construction",
        "/bids/professional-services",
        "/resources",
        "/sources",
    ]
    entries = [(f"{SITE_URL}{path}", None) for path in paths]
    has_public_notices = False
    for opp in load_public_opps():
        record = enrich(opp)
        if record.get("status") not in ("open", "upcoming"):
            continue
        if record.get("noise_flagged") or not record.get("id"):
            continue
        # The canonical crawler feed contains public procurement notices whose
        # notice_type is their category (construction or professional services).
        has_public_notices = has_public_notices or bool(record.get("_canonical_notice"))
        lastmod = record.get("last_verified_date")
        entries.append((f"{SITE_URL}/opportunities/{record['id']}", lastmod))
    if has_public_notices:
        entries.append((f"{SITE_URL}/notices", None))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for location, lastmod in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(location)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{escape(lastmod)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return Response("\n".join(lines), mimetype="application/xml")


HOMEPAGE_ACCESS_PLATFORMS = (
    "bid express",
    "bidnet",
    "njstart",
    "opengov",
    "planetbids",
    "questcdn",
)


def _homepage_platform(record: dict) -> str:
    """Only surface platforms that change how a contractor gets bid documents."""
    platform = str(record.get("platform") or "").strip()
    normalized = platform.lower()
    if any(name in normalized for name in HOMEPAGE_ACCESS_PLATFORMS):
        return platform
    return ""


def _latest_homepage_update(records: list[dict]) -> str | None:
    latest = None
    for record in records:
        value = record.get("crawled_at") or record.get("created_at")
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if latest is None or parsed.astimezone(timezone.utc) > latest:
            latest = parsed.astimezone(timezone.utc)
    return format_eastern_timestamp(latest.isoformat()) if latest else None


def _homepage_today() -> date:
    return datetime.now(EASTERN).date()


def _homepage_deadline_time(record: dict) -> str:
    """Render only a published bid time; date-only records stay silent."""
    if not record.get("deadline_has_time") or not record.get("deadline_local"):
        return ""
    try:
        local = datetime.fromisoformat(str(record["deadline_local"]))
    except (TypeError, ValueError):
        return ""
    rendered = local.strftime("%I:%M %p").lstrip("0") + " ET"
    if record.get("deadline_timezone_assumed"):
        rendered += " (time zone assumed)"
    return rendered


def _homepage_pipeline_window(record: dict) -> str:
    """Use the agency's published planning window without turning it into a deadline."""
    raw = str(record.get("due_date_raw") or "").strip()
    return raw or "Timing not published"


def _group_homepage_lane(records: list[dict], today: date) -> list[dict]:
    """Group a lane by its normalized Eastern closing date, soonest first."""
    groups: dict[str, dict] = {}
    for record in sort_opps(records):
        due = None if record.get("deadline_conflict") else deadline_date(record)
        key = due.isoformat() if due else "undated"
        if key not in groups:
            if due:
                days_remaining = (due - today).days
                if days_remaining == 0:
                    timing = "today"
                elif days_remaining == 1:
                    timing = "in 1 day"
                else:
                    timing = f"in {days_remaining} days"
                heading = f"Closes {due.strftime('%A, %b %d').replace(' 0', ' ')} - {timing}"
                urgency = "urgent" if days_remaining <= 2 else "soon" if days_remaining <= 7 else "future"
            else:
                days_remaining = None
                heading = "Closing date not confirmed"
                urgency = "undated"
            groups[key] = {
                "key": key,
                "heading": heading,
                "days_remaining": days_remaining,
                "urgency": urgency,
                "opportunities": [],
            }
        record["homepage_deadline_time"] = _homepage_deadline_time(record)
        groups[key]["opportunities"].append(record)
    return list(groups.values())


@app.route("/")
def index():
    opps = [enrich(opp) for opp in load_public_opps()]
    opps = [opp for opp in opps if opp["status"] not in ("noise", "deleted", "disabled")]
    active = sort_opps([opp for opp in opps if opp["status"] in ("open", "upcoming")])
    today = _homepage_today()
    for opp in active:
        opp["days_until_due"] = None if opp.get("deadline_conflict") else deadline_days_remaining(opp, today)
        opp["homepage_platform"] = _homepage_platform(opp)

    open_now = [opp for opp in active if opp["status"] == "open"]
    pipeline = [opp for opp in active if opp["status"] == "upcoming"]
    for opp in pipeline:
        opp["homepage_pipeline_window"] = _homepage_pipeline_window(opp)

    corridor_counts: dict[str, int] = {}
    for opp in active:
        for corridor in opp.get("corridors") or []:
            corridor_counts[corridor] = corridor_counts.get(corridor, 0) + 1
    top_corridors = sorted(corridor_counts.items(), key=lambda item: (-item[1], item[0]))[:10]

    construction = [opp for opp in active if opp.get("record_type") == "construction"]
    professional = [opp for opp in active if opp.get("record_type") == "professional_services"]
    public_sources = load_public_sources()
    stats = {
        "construction": len(construction),
        "professional_services": len(professional),
        "active": len(active),
        "open": len(open_now),
        "pipeline": len(pipeline),
        "open_construction": len(
            [opp for opp in open_now if opp.get("record_type") == "construction"]
        ),
        "open_professional": len(
            [opp for opp in open_now if opp.get("record_type") == "professional_services"]
        ),
        "pipeline_construction": len(
            [opp for opp in pipeline if opp.get("record_type") == "construction"]
        ),
        "pipeline_professional": len(
            [opp for opp in pipeline if opp.get("record_type") == "professional_services"]
        ),
        "closing_week": len(
            [
                opp
                for opp in open_now
                if opp.get("days_until_due") is not None
                and 0 <= opp["days_until_due"] <= 7
            ]
        ),
        "sources": len(public_sources),
        "healthy_sources": len([source for source in public_sources if source.get("severity") == "ok"]),
        "last_updated": _latest_homepage_update(opps),
    }
    return render_template(
        "index.html",
        stats=stats,
        top_corridors=top_corridors,
        open_lane=_group_homepage_lane(open_now[:10], today),
        pipeline_preview=sort_opps(pipeline)[:6],
        unclassified_open=len(
            [
                opp
                for opp in open_now
                if opp.get("record_type") not in ("construction", "professional_services")
            ]
        ),
    )


@app.route("/resources")
def contractor_resources():
    return render_template(
        "resources.html",
        resource_sections=RESOURCE_SECTIONS,
        resource_count=resource_count(),
    )


def _opp_list_view(record_type: str, notice_subtype: str | None = None) -> dict:
    opps = [enrich(opp) for opp in load_public_opps()]
    opps = [opp for opp in opps if opp["status"] != "deleted"]
    county = request.args.get("county", "")
    agency = request.args.get("agency", "")
    status = request.args.get("status", "active")
    show_closed = request.args.get("show_closed") == "1"
    q = request.args.get("q", "").lower()

    def keep(opp: dict) -> bool:
        current_status = opp["status"]
        is_closed = current_status in ("expired", "noise")
        if current_status in ("deleted", "disabled"):
            return False
        if status == "active" and current_status not in ("open", "upcoming") and not (show_closed and is_closed):
            return False
        if status == "all" and current_status not in ("open", "upcoming", "review_required", "ai_review", "unknown_date") and not (show_closed and is_closed):
            return False
        if status == "review" and current_status not in ("review_required", "ai_review", "unknown_date"):
            return False
        if status == "expired" and current_status != "expired":
            return False
        if current_status == "noise" and not show_closed:
            return False
        if opp["record_type"] != record_type:
            return False
        if notice_subtype and opp.get("notice_subtype") != notice_subtype:
            return False
        if county and county not in opp.get("counties", []):
            return False
        if agency and (opp.get("source_name") or "").lower() != agency.lower():
            return False
        if q and not matches_search(opp, q):
            return False
        return True

    filtered = sort_opps([opp for opp in opps if keep(opp)])
    soon, this_month, upcoming, nodate, closed = group_opportunity_scan(filtered)
    available_counties = {county for opp in opps for county in opp.get("counties", [])}
    counties = [county for county in NJ_COUNTIES if county in available_counties]
    agencies = sorted({opp.get("source_name", "") for opp in opps if opp.get("source_name")})
    today = date.today()
    soon_cutoff = today + timedelta(days=7)
    return {
        "soon": soon,
        "this_month": this_month,
        "upcoming": upcoming,
        "nodate": nodate,
        "closed": closed,
        "counties": counties,
        "agencies": agencies,
        "selected_county": county,
        "selected_agency": agency,
        "selected_status": status,
        "show_closed": show_closed,
        "q": q,
        "total": len(filtered),
        "open_count": len([opp for opp in filtered if opp.get("status") == "open"]),
        "upcoming_count": len([opp for opp in filtered if opp.get("status") == "upcoming"]),
        "mapped_count": len([opp for opp in filtered if opp.get("map_url")]),
        "agency_count": len(
            {opp.get("source_name") for opp in filtered if opp.get("source_name")}
        ),
        "last_verified": _latest_homepage_update(filtered),
        "record_type": record_type,
        "notice_subtype": notice_subtype,
        "today": today.isoformat(),
        "soon_cutoff": soon_cutoff.isoformat(),
    }


@app.route("/bids/construction")
def bids_construction():
    ctx = _opp_list_view("construction")
    ctx["page_title"] = "Construction Bids"
    ctx["seo_title"] = "Open NJDOT and NJ Transportation Construction Bids"
    ctx["page_desc"] = "Formal bids for roadway, bridge, drainage, pavement, and related heavy highway construction work."
    ctx["seo_description"] = (
        "Find open NJDOT, NJTA, county, and municipal roadway, bridge, drainage, "
        "paving, and heavy construction bids across New Jersey."
    )
    return render_template("opportunity_list.html", **ctx)


@app.route("/bids/professional-services")
def bids_profserv():
    ctx = _opp_list_view("professional_services")
    ctx["page_title"] = "Professional Services"
    ctx["seo_title"] = "NJ Transportation Engineering RFPs and Professional Services"
    ctx["page_desc"] = "RFPs and RFQs for engineering, design, inspection, planning, and related consulting services."
    ctx["seo_description"] = (
        "Find open NJDOT, NJTA, county, and municipal engineering RFPs, design, "
        "inspection, planning, and professional services opportunities."
    )
    return render_template("opportunity_list.html", **ctx)


@app.route("/opportunities")
def opportunities():
    return redirect(url_for("bids_construction"))


@app.route("/opportunities/<opp_id>")
def opportunity_detail(opp_id: str):
    opportunities = [enrich(item) for item in load_public_opps()]
    opp = next((item for item in opportunities if str(item.get("id")) == opp_id), None)
    if not opp or opp["status"] == "deleted":
        return "Not found", 404
    related = rank_related(opp, opportunities, limit=4)
    seo = build_opportunity_seo(opp)
    return render_template(
        "opportunity_detail.html",
        opp=opp,
        related=related,
        readiness=readiness_for(opp),
        source_total=len(NOTICE_SOURCES),
        seo_title=seo["title"],
        seo_description=seo["description"],
    )


@app.route("/opportunities/<opp_id>/calendar.ics")
def opportunity_calendar(opp_id: str):
    opp = next((enrich(item) for item in load_public_opps() if str(item.get("id")) == opp_id), None)
    if not opp or opp.get("deadline_conflict") or not opp.get("due_date_parsed") or opp.get("status") not in ("open", "upcoming"):
        return "Calendar event not available", 404

    def ics_text(value):
        return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    detail_url = f"{SITE_URL}/opportunities/{opp_id}"
    event_lines = []
    if opp.get("deadline_precision") == "datetime" and opp.get("deadline_at"):
        event_at = datetime.fromisoformat(opp["deadline_at"].replace("Z", "+00:00"))
        event_lines.append(f"DTSTART:{event_at.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    else:
        event_date = date.fromisoformat(opp["due_date_parsed"])
        next_date = event_date + timedelta(days=1)
        event_lines.extend(
            [
                f"DTSTART;VALUE=DATE:{event_date.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{next_date.strftime('%Y%m%d')}",
            ]
        )

    description = " - ".join(
        part
        for part in (
            opp.get("source_name"),
            f"Source deadline: {opp.get('due_date_raw')}" if opp.get("due_date_raw") else None,
            "Verify submission details with the official source.",
        )
        if part
    )
    calendar = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//NJ Transportation Bids//Bid Deadline//EN",
            "BEGIN:VEVENT",
            f"UID:{ics_text(opp_id)}@njtransportationbids.com",
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            *event_lines,
            f"SUMMARY:{ics_text('Bid due: ' + opp.get('title', 'Opportunity'))}",
            f"DESCRIPTION:{ics_text(description)}",
            f"URL:{detail_url}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return Response(
        calendar,
        mimetype="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{opp_id}-deadline.ics"'},
    )


@app.route("/sources")
def sources():
    sources = load_public_sources()
    opps = [enrich(opp) for opp in load_public_opps()]
    for source in sources:
        source_id = source.get("id")
        related = [opp for opp in opps if opp.get("source_id") == source_id]
        source["total"] = len(related)
        source["noise"] = len([opp for opp in related if opp["status"] == "noise"])
        source["expired"] = len([opp for opp in related if opp["status"] == "expired"])
        source["open"] = len([opp for opp in related if opp["status"] == "open"])
        source["upcoming"] = len([opp for opp in related if opp["status"] == "upcoming"])
        source["review_required"] = len([opp for opp in related if opp["status"] == "review_required"])
        source["ai_review"] = len([opp for opp in related if opp["status"] == "ai_review"])
    sources = sorted(sources, key=lambda source: source.get("name", "").lower())
    source_summary = {
        "configured": len(sources),
        "healthy": len([source for source in sources if source.get("severity") == "ok"]),
        "warning": len([source for source in sources if source.get("severity") == "warning"]),
        "error": len([source for source in sources if source.get("severity") == "error"]),
        "state": len([source for source in sources if source.get("tier") == "state"]),
        "county": len([source for source in sources if source.get("tier") == "county"]),
        "municipal": len([source for source in sources if source.get("tier") == "municipal"]),
        "platform": len([source for source in sources if source.get("tier") == "paywalled"]),
    }
    return render_template("sources.html", sources=sources, source_summary=source_summary)


@app.route("/export/opportunities.csv")
def export_csv():
    ids = request.args.get("ids", "")
    selected = {item for item in ids.split(",") if item}
    opps = [enrich(opp) for opp in load_public_opps()]
    opps = [opp for opp in opps if opp["status"] in ("open", "upcoming")]
    if selected:
        opps = [opp for opp in opps if str(opp.get("id")) in selected]

    buf = StringIO()
    fields = [
        "id",
        "title",
        "source_name",
        "county",
        "county_provenance",
        "counties",
        "coverage_scope",
        "region_raw",
        "geography_confidence",
        "geography_provenance",
        "geography_evidence",
        "agency_county_hint",
        "geography_review_required",
        "record_type",
        "notice_subtype",
        "due_date_raw",
        "due_date_parsed",
        "deadline_at",
        "deadline_local",
        "deadline_timezone",
        "deadline_timezone_source",
        "deadline_timezone_assumed",
        "deadline_precision",
        "deadline_display",
        "status",
        "access_type",
        "platform",
        "official_url",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    export_rows = [{**opp, "counties": "|".join(opp.get("counties", []))} for opp in opps]
    writer.writerows(export_rows)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="njtbids-opportunities.csv"'},
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and _check_pw(request.form.get("password", "")):
            session["admin"] = True
            session.permanent = False
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        error = "Invalid username or password."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    opps = [enrich(opp) for opp in load_opps()]
    opps = [opp for opp in opps if opp["status"] not in ("deleted", "disabled")]
    active = [opp for opp in opps if opp["status"] == "open"]
    stats = {
        "open": len([opp for opp in opps if opp["status"] == "open"]),
        "review_required": len([opp for opp in opps if opp["status"] == "review_required"]),
        "ai_review": len([opp for opp in opps if opp["status"] == "ai_review"]),
        "total": len(opps),
        "noise": len([opp for opp in opps if opp["status"] == "noise"]),
        "expired": len([opp for opp in opps if opp["status"] == "expired"]),
        "construction": len([opp for opp in active if opp["record_type"] == "construction"]),
        "profserv": len([opp for opp in active if opp["record_type"] == "professional_services"]),
        "notices": len([opp for opp in active if opp["record_type"] == "public_notice"]),
        "uncat": len([opp for opp in active if opp["record_type"] == "uncategorized"]),
    }
    return render_template("admin_dashboard.html", stats=stats)


@app.route("/admin/records")
@admin_required
def admin_records():
    opps = [enrich(opp) for opp in load_opps()]
    opps = [opp for opp in opps if opp["status"] != "deleted"]
    filt = request.args.get("filter", "all")
    q = request.args.get("q", "").lower()
    source_name = request.args.get("source", "")
    selected_type = request.args.get("type", "")

    def keep(opp: dict) -> bool:
        if filt == "review" and opp["status"] not in ("review_required", "ai_review"):
            return False
        if filt == "noise" and opp["status"] != "noise":
            return False
        if filt == "expired" and opp["status"] != "expired":
            return False
        if filt == "nodate" and opp["status"] != "review_required":
            return False
        if filt == "ai" and opp["status"] != "ai_review":
            return False
        if filt == "uncat" and opp["record_type"] != "uncategorized":
            return False
        if selected_type and opp["record_type"] != selected_type:
            return False
        if source_name and opp.get("source_name", "") != source_name:
            return False
        haystack = f"{opp.get('title', '')} {opp.get('source_name', '')}".lower()
        if q and q not in haystack:
            return False
        return True

    filtered = [opp for opp in opps if keep(opp)]
    sources = sorted({opp.get("source_name", "") for opp in opps if opp.get("source_name")})
    return render_template(
        "admin_records.html",
        records=filtered,
        filt=filt,
        q=q,
        selected_source=source_name,
        selected_type=selected_type,
        sources=sources,
        total=len(filtered),
        all_total=len(opps),
    )


@app.route("/admin/api/bulk", methods=["POST"])
@admin_required
def admin_bulk():
    data = request.get_json() or {}
    action = data.get("action")
    ids = [str(item) for item in data.get("ids", [])]
    record_type = data.get("record_type")
    notice_subtype = data.get("notice_subtype")
    if action not in {"delete", "noise", "approve", "restore", "set_type"}:
        return jsonify({"ok": False, "msg": "Unknown action"}), 400
    if not ids:
        return jsonify({"ok": False, "msg": "No records selected"}), 400
    if action == "set_type" and not record_type:
        return jsonify({"ok": False, "msg": "No record type provided"}), 400
    changed = update_leads(ids, action, record_type=record_type, notice_subtype=notice_subtype)
    return jsonify({"ok": True, "changed": changed})


@app.route("/admin/api/record/<opp_id>", methods=["PATCH", "DELETE"])
@admin_required
def admin_record(opp_id: str):
    if request.method == "DELETE":
        changed = update_leads([opp_id], "delete")
        return jsonify({"ok": bool(changed)})

    patch = request.get_json() or {}
    ok = patch_lead(opp_id, patch)
    return jsonify({"ok": ok})


@app.route("/admin/api/rescore", methods=["POST"])
@admin_required
def admin_rescore():
    rescored = clear_noise_flags()
    return jsonify({"ok": True, "rescored": rescored})


@app.route("/admin/sources")
@admin_required
def admin_sources():
    sources = load_sources()
    opps = [enrich(opp) for opp in load_opps()]
    for source in sources:
        source_id = source.get("id")
        related = [opp for opp in opps if opp.get("source_id") == source_id]
        source["total"] = len(related)
        source["noise"] = len([opp for opp in related if opp["status"] == "noise"])
        source["expired"] = len([opp for opp in related if opp["status"] == "expired"])
        source["open"] = len([opp for opp in related if opp["status"] == "open"])
        source["review_required"] = len([opp for opp in related if opp["status"] == "review_required"])
        source["ai_review"] = len([opp for opp in related if opp["status"] == "ai_review"])
        ratio = source["noise"] / max(source["total"], 1)
        source["health"] = "bad" if ratio > 0.4 else "warn" if ratio > 0.15 else "good"
    sources = sorted(sources, key=lambda s: (-s.get("crawlability_score", 0), s.get("name", "").lower()))
    return render_template("admin_sources.html", sources=sources)


init_db_schema()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=True)
