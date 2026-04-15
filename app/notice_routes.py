"""
notice_routes.py
----------------
Flask routes for the public notice feed.

Register in app/main.py:
    from app.notice_routes import notice_bp
    app.register_blueprint(notice_bp)

This replaces / extends your existing /notices routes.
notices.json is loaded from data/notices/ — written by notice_runner.py.
The existing opportunities.json still powers /bids/construction etc.
"""

import os, json, csv
from datetime import datetime, date
from io import StringIO
from flask import (Blueprint, render_template, request,
                   redirect, url_for, Response, session)

notice_bp = Blueprint("notices2", __name__)

# ── Data ──────────────────────────────────────────────────────────────────────

BASE        = os.path.join(os.path.dirname(__file__), "..")
NOTICES_F   = os.path.join(BASE, "data", "notices", "notices.json")
CRAWL_LOG_F = os.path.join(BASE, "data", "notices", "crawl_log.json")

NJ_COUNTIES = [
    "Atlantic","Bergen","Burlington","Camden","Cape May","Cumberland",
    "Essex","Gloucester","Hudson","Hunterdon","Mercer","Middlesex",
    "Monmouth","Morris","Ocean","Passaic","Salem","Somerset",
    "Sussex","Union","Warren","Statewide",
]

def _load_notices():
    if not os.path.exists(NOTICES_F): return []
    with open(NOTICES_F, encoding="utf-8") as f:
        return json.load(f)

def _load_crawl_log():
    if not os.path.exists(CRAWL_LOG_F): return []
    with open(CRAWL_LOG_F, encoding="utf-8") as f:
        return json.load(f)

def _fmt_ago(iso):
    if not iso: return "unknown"
    try:
        dt = datetime.fromisoformat(iso.replace("Z","+00:00"))
        diff = datetime.now(dt.tzinfo) - dt
        s = int(diff.total_seconds())
        if s < 60:   return "just now"
        if s < 3600: return f"{s//60}m ago"
        if s < 86400:return f"{s//3600}h ago"
        return f"{s//86400}d ago"
    except: return ""

def _source_health(crawl_log):
    """Return {source_id: health_dict} from crawl log."""
    return {e["source_id"]: e for e in crawl_log}

# ── Filtering helpers ─────────────────────────────────────────────────────────

def _filter_notices(notices, notice_type=None, notice_subtype=None,
                    county=None, agency=None, status_filter="active",
                    source_tier=None, q=None, urgent_only=False):
    today = date.today()
    out = []
    for n in notices:
        if n.get("status") == "deleted": continue
        if n.get("noise_flagged") and n.get("status") != "approved": continue

        # Status
        st = n.get("status","")
        if status_filter == "active"  and st not in ("open","unknown_date"): continue
        if status_filter == "expired" and st != "expired":                   continue
        if status_filter == "urgent"  and not n.get("urgent"):               continue

        # Type
        if notice_type and n.get("notice_type") != notice_type:             continue

        # Subtype — allow "construction" to match both notice_subtype=construction
        # and notice_type=construction
        if notice_subtype:
            if n.get("notice_subtype") != notice_subtype and n.get("notice_type") != notice_subtype:
                continue

        # County
        if county:
            nc = (n.get("county") or "").lower()
            if county.lower() not in nc and nc not in ("statewide",""):
                if county.lower() != "statewide":
                    continue

        # Agency / source
        if agency and (n.get("source_name","").lower() != agency.lower()): continue

        # Source tier
        if source_tier and n.get("source_tier") != source_tier: continue

        # Search
        if q:
            ql = q.lower()
            searchable = " ".join([
                n.get("title",""),
                n.get("notice_excerpt",""),
                n.get("source_name",""),
                n.get("contract_number",""),
                n.get("county",""),
            ]).lower()
            if ql not in searchable: continue

        if urgent_only and not n.get("urgent"): continue

        out.append(n)
    return out


def _sort_notices(notices):
    """Sort: urgent open first, then open by due date, then no-date, then expired."""
    def key(n):
        st = n.get("status","")
        urgent = n.get("urgent", False)
        due    = n.get("due_date_parsed") or "9999"
        if urgent:             return (0, due)
        if st == "open":       return (1, due)
        if st == "unknown_date": return (2, due)
        return (3, due)
    return sorted(notices, key=key)


def _group_by_urgency(notices):
    today = date.today()
    urgent, week, month, nodate, expired = [], [], [], [], []
    for n in notices:
        st  = n.get("status","")
        due = n.get("due_date_parsed")

        if st == "expired":
            expired.append(n)
            continue

        if not due:
            nodate.append(n)
            continue

        days = (date.fromisoformat(due) - today).days
        if days <= 7:   urgent.append(n)
        elif days <= 30: week.append(n)
        else:            month.append(n)

    return urgent, week, month, nodate, expired


def _build_stats(notices):
    active   = [n for n in notices if n.get("status") in ("open","unknown_date")
                and not n.get("noise_flagged")]
    today    = date.today()
    posted_today = [n for n in active
                    if (n.get("crawled_at") or "")[:10] == today.isoformat()]
    due_week = [n for n in active if n.get("due_date_parsed") and
                (date.fromisoformat(n["due_date_parsed"]) - today).days <= 7]

    # Count by source tier
    state_ct  = len([n for n in active if n.get("source_tier") == "state"])
    county_ct = len([n for n in active if n.get("source_tier") == "county"])
    munic_ct  = len([n for n in active if n.get("source_tier") == "municipal"])

    return {
        "active":       len(active),
        "due_week":     len(due_week),
        "posted_today": len(posted_today),
        "state":        state_ct,
        "county":       county_ct,
        "municipal":    munic_ct,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

def _notice_list_view(notice_type=None, notice_subtype=None, active_nav="notices_all"):
    notices     = _load_notices()
    crawl_log   = _load_crawl_log()
    health      = _source_health(crawl_log)

    # Last successful crawl info
    last_crawls = sorted(
        [e.get("last_crawl","") for e in crawl_log if e.get("last_crawl")],
        reverse=True
    )
    last_crawl_ago = _fmt_ago(last_crawls[0]) if last_crawls else "unknown"

    # Filter params
    county       = request.args.get("county","")
    agency       = request.args.get("agency","")
    source_tier  = request.args.get("tier","")
    status_filter= request.args.get("status","active")
    q            = request.args.get("q","").strip()

    filtered = _filter_notices(
        notices,
        notice_type=notice_type,
        notice_subtype=notice_subtype,
        county=county or None,
        agency=agency or None,
        status_filter=status_filter,
        source_tier=source_tier or None,
        q=q or None,
    )
    sorted_notices = _sort_notices(filtered)
    urgent, week, month, nodate, expired = _group_by_urgency(sorted_notices)
    stats = _build_stats(notices)

    # Build filter options from full dataset
    all_active = _filter_notices(notices, notice_type=notice_type,
                                 notice_subtype=notice_subtype, status_filter="active")
    agencies = sorted(set(n.get("source_name","") for n in all_active if n.get("source_name")))

    return render_template("notices/notice_list.html",
        urgent=urgent, week=week, month=month,
        nodate=nodate, expired=expired,
        total=len(filtered),
        stats=stats,
        counties=NJ_COUNTIES,
        agencies=agencies,
        selected_county=county,
        selected_agency=agency,
        selected_tier=source_tier,
        selected_status=status_filter,
        q=q,
        notice_type=notice_type,
        notice_subtype=notice_subtype,
        active_nav=active_nav,
        last_crawl_ago=last_crawl_ago,
        user=session.get("user_id"),
    )


@notice_bp.route("/notices")
def notices_all():
    return _notice_list_view(active_nav="notices_all")

@notice_bp.route("/notices/construction")
def notices_construction():
    return _notice_list_view(notice_subtype="construction",
                             active_nav="notices_construction")

@notice_bp.route("/notices/professional-services")
def notices_profserv():
    return _notice_list_view(notice_subtype="professional_services",
                             active_nav="notices_profserv")

@notice_bp.route("/notices/<notice_id>")
def notice_detail(notice_id):
    notices = _load_notices()
    notice  = next((n for n in notices if n.get("id") == notice_id), None)
    if not notice:
        return "Notice not found", 404
    notice["_ago"] = _fmt_ago(notice.get("crawled_at",""))
    return render_template("notices/notice_detail.html",
                           notice=notice, user=session.get("user_id"))


@notice_bp.route("/export/notices.csv")
def export_notices_csv():
    notices = _load_notices()
    active  = [n for n in notices if n.get("status") in ("open","unknown_date")
               and not n.get("noise_flagged")]
    buf = StringIO()
    fields = ["id","title","source_name","source_tier","county","notice_type",
              "notice_subtype","due_date_raw","due_date_parsed","status",
              "contract_number","access_type","platform","paywalled","official_url"]
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(active)
    return Response(buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition":"attachment; filename=njtbids-notices.csv"})


# ── Admin: crawl health ───────────────────────────────────────────────────────

@notice_bp.route("/admin/notices/health")
def admin_notice_health():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    crawl_log = _load_crawl_log()
    notices   = _load_notices()
    stats     = _build_stats(notices)
    # Annotate log with source metadata
    from crawlers.notice_sources import SOURCES_BY_ID
    for e in crawl_log:
        src = SOURCES_BY_ID.get(e.get("source_id",""),{})
        e["source_name"] = src.get("name", e.get("source_id",""))
        e["crawl_tier"]  = src.get("crawl_tier","")
        e["ago"]         = _fmt_ago(e.get("last_crawl",""))
    crawl_log.sort(key=lambda e: (e.get("crawl_tier",9), e.get("source_name","")))
    return render_template("notices/admin_health.html",
                           crawl_log=crawl_log, stats=stats)
