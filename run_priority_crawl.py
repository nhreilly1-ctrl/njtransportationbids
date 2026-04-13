from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import os
import re
import secrets
import html as html_lib
import psycopg2
import requests
from bs4 import BeautifulSoup
from psycopg2.extras import RealDictCursor

from app.core.filters import clean_title, is_garbage_title


HEADERS = {
    "User-Agent": "NJTransportationBidsBot/0.3 (+manual-priority-crawl)"
}

PRIORITY_TIERS = ("Tier 1", "Tier 2")

SOURCE_RULES = {
    "state-njdot-construction": "trusted",
    "state-njdot-profserv": "trusted",
    "state-drjtbc-construction": "trusted",
    "state-drjtbc-profserv": "trusted",
    "state-njta": "trusted",
    "state-njtransit": "trusted",
    "state-panynj-construction": "trusted",
    "state-panynj-profserv": "trusted",
    "county-camden": "ai_review",
    "county-burlington": "ai_review",
    "municipal-jersey-city": "ai_review",
    "municipal-hoboken": "ai_review",
    "county-bergen": "ai_review",
    "county-essex": "manual_review",
    "municipal-paterson": "manual_review",
    "municipal-elizabeth": "manual_review",
    "county-cape-may": "manual_review",
    "county-hudson": "manual_review",
    "municipal-camden": "manual_review",
    "county-cumberland": "manual_review",
    "county-gloucester": "manual_review",
    "county-hunterdon": "manual_review",
    "municipal-newark": "metadata_only",
    "county-atlantic": "disabled",
    "county-mercer": "disabled",
    "municipal-trenton": "disabled",
}

RESTOCK_SOURCE_IDS = {
    "state-njdot-construction",
    "state-njdot-profserv",
    "state-drjtbc-construction",
    "state-drjtbc-profserv",
    "state-njta",
    "state-njtransit",
    "state-panynj-construction",
    "state-panynj-profserv",
    "county-camden",
    "county-burlington",
    "municipal-jersey-city",
    "municipal-hoboken",
    "county-bergen",
    "county-essex",
    "municipal-paterson",
}


@dataclass
class CrawlResult:
    status: str
    records_found: int
    records_promoted: int


DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
PROFSERV_DETAIL_RE = re.compile(r"^(?P<desc>.+?)\s+(?:Advertised|Pending Selection)\s+(?P<due>\d{1,2}/\d{1,2}/\d{4})$")
LEVEL_CODE_RE = re.compile(r"^[A-Z]-\d+\s+Level\s+[A-Z]$", re.IGNORECASE)
NJT_QUOTED_TITLE_RE = re.compile(r'"([^"]+)"')
NJT_NUMBER_RE = re.compile(r"\b((?:IFB|RFP|RFQ)\s+No\.\s*[\w-]+)\b", re.IGNORECASE)


def get_conn():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set in this PowerShell window.")
    if db_url.startswith("postgresql+psycopg2://"):
        db_url = "postgresql://" + db_url[len("postgresql+psycopg2://"):]
    return psycopg2.connect(db_url)


def get_table_columns(conn, table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        return {row[0] for row in cur.fetchall()}


def pick_source_url(source: dict[str, Any], source_cols: set[str]) -> str | None:
    for key in (
        "source_url",
        "effective_notice_entry_url",
        "primary_procurement_url",
        "direct_legal_notice_url",
    ):
        if key in source_cols and source.get(key):
            return source[key]
    return None


def fetch_page(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def parse_njdot_construction(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    current_due = ""

    content = soup.find(id="content") or soup
    lines = [clean_title(text) for text in content.stripped_strings]
    links = {
        clean_title(anchor.get_text(" ", strip=True)).rstrip("."): urljoin(base_url, anchor["href"])
        for anchor in content.find_all("a", href=True)
    }

    started = False
    for text in lines:
        if not text:
            continue
        if text == "CURRENTLY ADVERTISED PROJECTS":
            started = True
            current_due = ""
            continue
        if not started:
            continue
        if text in {"NJDOT", "About NJDOT", "Capital Program"}:
            break
        if DATE_RE.match(text):
            current_due = text
            continue
        if text.startswith("The New Jersey Department of Transportation is holding a Voluntary Pre-Bid Meeting"):
            continue
        title = text.rstrip(".")
        href = links.get(title)
        if not href:
            continue
        if is_garbage_title(title):
            continue
        key = (title.lower(), href)
        if key in seen:
            continue
        seen.add(key)
        item = {"title": title, "url": href}
        if current_due:
            item["due_date"] = current_due
        items.append(item)
    return items[:50]


def parse_njdot_profserv(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    content = soup.find(id="content") or soup
    table = content.select_one("table")
    if not table:
        return items
    for row in table.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 6:
            continue
        tp_anchor = cells[0].find("a", href=True)
        tp_number = clean_title(cells[0].get_text(" ", strip=True)).split()[0] if cells[0].get_text(" ", strip=True) else ""
        if not tp_anchor or not tp_number.startswith("TP-"):
            continue
        href = urljoin(base_url, tp_anchor["href"])
        project_type_parts = [clean_title(part) for part in cells[2].stripped_strings]
        project_type_parts = [part for part in project_type_parts if part and not LEVEL_CODE_RE.match(part)]
        project_type = clean_title(" ".join(project_type_parts))
        desc_parts = [clean_title(part) for part in cells[3].stripped_strings]
        desc = clean_title(" ".join(part for part in desc_parts if part))
        if not desc:
            continue
        due_date = clean_title(cells[5].get_text(" ", strip=True))
        title = f"{tp_number} - {desc}"
        if project_type and project_type.lower() not in desc.lower():
            title = f"{project_type}: {title}"
        if is_garbage_title(title):
            continue
        key = (title.lower(), href)
        if key in seen:
            continue
        seen.add(key)
        item = {"title": title, "url": href}
        if DATE_RE.match(due_date):
            item["due_date"] = due_date
        items.append(item)

    return items[:50]


def extract_njtransit_body_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        text = script.get_text(" ", strip=True)
        if "table id=\\\"proc-cal\\\"" not in text:
            continue
        start = text.find("\\u003Cdiv")
        end = text.find('\\"id\\":')
        if start == -1:
            start = text.find("\\u003Cdl")
        if start == -1 or end == -1:
            continue
        blob = text[start:end].rstrip(", ")
        decoded = blob.encode("utf-8").decode("unicode_escape")
        decoded = decoded.replace("\\u003C", "<").replace("\\u003E", ">").replace("\\u0026", "&")
        decoded = decoded.replace('\\"', '"').replace("\\/", "/")
        return html_lib.unescape(decoded)
    return ""


def parse_njtransit_calendar(html: str, base_url: str) -> list[dict[str, str]]:
    body_html = extract_njtransit_body_html(html)
    if not body_html:
        return []
    soup = BeautifulSoup(body_html, "html.parser")
    table = soup.select_one("table#proc-cal")
    if not table:
        return []

    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        event_date = clean_title(cells[0].get_text(" ", strip=True))
        desc_cell = cells[2]
        desc_text = clean_title(desc_cell.get_text(" ", strip=True))
        ref_text = clean_title(cells[3].get_text(" ", strip=True))
        link = desc_cell.find("a", href=True)
        href = urljoin(base_url, link["href"]) if link else base_url

        quoted = NJT_QUOTED_TITLE_RE.search(desc_text)
        ref_match = NJT_NUMBER_RE.search(ref_text or desc_text)
        ref_number = clean_title(ref_match.group(1)) if ref_match else ref_text
        project_title = clean_title(quoted.group(1)) if quoted else ""
        if not project_title:
            project_title = desc_text.split(" General navigation", 1)[0]
            project_title = project_title.split(" NOTE:", 1)[0]
        project_title = clean_title(project_title.replace("Electronic Bids Due for", "").replace("Proposals Due:", ""))
        title = clean_title(f"{ref_number} - {project_title}" if ref_number else project_title)
        if is_garbage_title(title):
            continue
        key = (title.lower(), href)
        if key in seen:
            continue
        seen.add(key)
        item = {"title": title, "url": href}
        if DATE_RE.match(event_date):
            item["due_date"] = event_date
        items.append(item)
    return items[:50]


def extract_items(source_id: str, html: str, base_url: str) -> list[dict[str, str]]:
    source_id = (source_id or "").lower()
    if source_id == "state-njdot-construction":
        items = parse_njdot_construction(html, base_url)
        if items:
            return items
    if source_id == "state-njdot-profserv":
        items = parse_njdot_profserv(html, base_url)
        if items:
            return items
    if source_id == "state-njtransit":
        items = parse_njtransit_calendar(html, base_url)
        if items:
            return items

    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    selectors = [
        "table tr",
        ".bid-item",
        ".solicitation-row",
        ".views-row",
        "article",
        "li",
        "a[href]",
    ]

    for selector in selectors:
        for node in soup.select(selector)[:100]:
            title = ""
            href = None

            link = node if getattr(node, "name", "") == "a" else node.select_one("a[href]")
            if link:
                href = link.get("href")
                title = link.get_text(" ", strip=True)

            if not title:
                title = node.get_text(" ", strip=True)

            title = clean_title(title)[:300]
            if is_garbage_title(title):
                continue

            if not href:
                href = base_url
            href = urljoin(base_url, href)

            key = (title.lower(), href)
            if key in seen:
                continue
            seen.add(key)
            items.append({"title": title, "url": href})

    return items[:50]


def load_sources(conn, source_cols: set[str]) -> list[dict[str, Any]]:
    select_fields = ["source_id"]
    for field in (
        "source_name",
        "county",
        "entity_type",
        "source_url",
        "effective_notice_entry_url",
        "primary_procurement_url",
        "direct_legal_notice_url",
        "priority_tier",
        "source_status",
        "import_enabled",
    ):
        if field in source_cols:
            select_fields.append(field)

    where_clauses: list[str] = []
    params: list[Any] = []

    if "import_enabled" in source_cols:
        where_clauses.append("COALESCE(import_enabled, TRUE) IS TRUE")
    if "source_status" in source_cols:
        where_clauses.append("COALESCE(source_status, '') != 'Inactive'")
    if "priority_tier" in source_cols:
        where_clauses.append("priority_tier = ANY(%s)")
        params.append(list(PRIORITY_TIERS))
    if "source_id" in source_cols:
        where_clauses.append("source_id = ANY(%s)")
        params.append(sorted(RESTOCK_SOURCE_IDS))

    query = f"SELECT {', '.join(select_fields)} FROM registry_sources"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    if "source_name" in source_cols:
        query += " ORDER BY source_name"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        rows = [dict(row) for row in cur.fetchall()]
        filtered: list[dict[str, Any]] = []
        for row in rows:
            source_id = (row.get("source_id") or "").lower()
            mode = SOURCE_RULES.get(source_id, "manual_review")
            if mode in {"disabled", "metadata_only"}:
                continue
            if source_id not in RESTOCK_SOURCE_IDS:
                continue
            filtered.append(row)
        return filtered


def get_existing_records(conn, lead_cols: set[str], source_id: str) -> list[dict[str, Any]]:
    title_col = "notice_title" if "notice_title" in lead_cols else "title"
    url_col = "notice_url" if "notice_url" in lead_cols else "source_url"
    due_col = "due_at" if "due_at" in lead_cols else "due_date" if "due_date" in lead_cols else None
    if title_col not in lead_cols or url_col not in lead_cols:
        return []

    where_clauses = ["source_id = %s"]
    params: list[Any] = [source_id]
    if "status_override" in lead_cols:
        where_clauses.append("COALESCE(status_override, '') != 'deleted'")

    select_cols = ["lead_id", f"COALESCE({title_col}, '') AS title_key", f"COALESCE({url_col}, '') AS url_key"]
    if due_col:
        select_cols.append(f"{due_col} AS due_value")
    if "source_url" in lead_cols:
        select_cols.append("COALESCE(source_url, '') AS source_url_value")

    query = f"""
        SELECT {', '.join(select_cols)}
        FROM opportunity_leads
        WHERE {' AND '.join(where_clauses)}
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def update_existing_due_date(conn, lead_cols: set[str], lead_id: Any, due_date: str) -> None:
    due_col = "due_at" if "due_at" in lead_cols else "due_date" if "due_date" in lead_cols else None
    if not due_col or not due_date:
        return
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE opportunity_leads
            SET {due_col} = %s
            WHERE lead_id = %s AND ({due_col} IS NULL OR CAST({due_col} AS text) = '')
            """,
            (due_date, lead_id),
        )


def update_existing_record(conn, lead_cols: set[str], existing: dict[str, Any], item: dict[str, str]) -> None:
    assignments: list[str] = []
    params: list[Any] = []

    existing_title = clean_title(existing.get("title_key"))
    new_title = clean_title(item.get("title"))
    if "title" in lead_cols and new_title and (
        not existing_title or is_garbage_title(existing_title) or len(new_title) > len(existing_title) + 10
    ):
        assignments.append("title = %s")
        params.append(new_title)

    if "source_url" in lead_cols and item.get("url") and not existing.get("source_url_value"):
        assignments.append("source_url = %s")
        params.append(item["url"])

    due_col = "due_at" if "due_at" in lead_cols else "due_date" if "due_date" in lead_cols else None
    if due_col and item.get("due_date") and not existing.get("due_value"):
        assignments.append(f"{due_col} = %s")
        params.append(item["due_date"])

    if not assignments:
        return

    params.append(existing["lead_id"])
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE opportunity_leads
            SET {', '.join(assignments)}
            WHERE lead_id = %s
            """,
            params,
        )


def build_insert_payload(
    *,
    lead_cols: set[str],
    source: dict[str, Any],
    item: dict[str, str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {"source_id": source["source_id"]}
    title = clean_title(item["title"])
    url = item["url"]
    source_name = source.get("source_name") or source["source_id"]

    if "notice_title" in lead_cols:
        payload["notice_title"] = title
        payload["notice_url"] = url
        if "official_url" in lead_cols:
            payload["official_url"] = url
        if "owner_name" in lead_cols:
            payload["owner_name"] = source_name
        if "owner_type" in lead_cols:
            payload["owner_type"] = source.get("entity_type")
        if "promotion_decision" in lead_cols:
            payload["promotion_decision"] = "Review"
        if "lead_status" in lead_cols:
            payload["lead_status"] = "new"
        if "verification_status" in lead_cols:
            payload["verification_status"] = "Unknown"
    else:
        payload["title"] = title
        if "source_url" in lead_cols:
            payload["source_url"] = url
        if "agency" in lead_cols:
            payload["agency"] = source_name
        if "status" in lead_cols:
            payload["status"] = "Review"

    if "county" in lead_cols:
        payload["county"] = source.get("county")
    if "due_date" in item:
        if "due_date" in lead_cols:
            payload["due_date"] = item["due_date"]
        if "due_at" in lead_cols:
            payload["due_at"] = item["due_date"]
    if "raw_text" in lead_cols:
        payload["raw_text"] = title
    if "created_at" in lead_cols:
        payload["created_at"] = datetime.now(timezone.utc)
    if "next_step" in lead_cols:
        payload["next_step"] = "Open the official source and review the bid notice."

    return {k: v for k, v in payload.items() if k in lead_cols}


def get_column_data_type(conn, table_name: str, column_name: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
            """,
            (table_name, column_name),
        )
        row = cur.fetchone()
        return row[0] if row else None


def build_lead_id(conn, source_id: str) -> str | int:
    lead_id_type = get_column_data_type(conn, "opportunity_leads", "lead_id")
    if lead_id_type in {"integer", "bigint", "smallint"}:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(MAX(CAST(lead_id AS bigint)), 0) + 1
                FROM opportunity_leads
                """
            )
            return int(cur.fetchone()[0])
    return f"lead-{source_id}-{secrets.token_hex(8)}"


def insert_lead(conn, payload: dict[str, Any], lead_cols: set[str], source_id: str) -> None:
    if "lead_id" in lead_cols and "lead_id" not in payload:
        payload["lead_id"] = build_lead_id(conn, source_id)
    columns = list(payload.keys())
    values = [payload[col] for col in columns]
    placeholders = ", ".join(["%s"] * len(columns))
    query = f"""
        INSERT INTO opportunity_leads ({', '.join(columns)})
        VALUES ({placeholders})
    """
    with conn.cursor() as cur:
        cur.execute(query, values)


def update_source_status(
    conn,
    *,
    source_id: str,
    source_cols: set[str],
    records_found: int,
    status: str,
) -> None:
    assignments: list[str] = []
    params: list[Any] = []

    if "last_crawl_at" in source_cols:
        assignments.append("last_crawl_at = %s")
        params.append(datetime.now(timezone.utc))
    if "last_crawl_status" in source_cols:
        assignments.append("last_crawl_status = %s")
        params.append(status)
    if "last_leads_found" in source_cols:
        assignments.append("last_leads_found = %s")
        params.append(records_found)

    if not assignments:
        return

    params.append(source_id)
    query = f"""
        UPDATE registry_sources
        SET {', '.join(assignments)}
        WHERE source_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(query, params)


def run_source_crawl(conn, source: dict[str, Any], *, source_cols: set[str], lead_cols: set[str]) -> CrawlResult:
    base_url = pick_source_url(source, source_cols)
    if not base_url:
        update_source_status(conn, source_id=source["source_id"], source_cols=source_cols, records_found=0, status="missing_url")
        conn.commit()
        return CrawlResult(status="missing_url", records_found=0, records_promoted=0)

    html = fetch_page(base_url)
    items = extract_items(source["source_id"], html, base_url)
    existing_rows = get_existing_records(conn, lead_cols, source["source_id"])
    existing_titles = {clean_title(row["title_key"]).lower() for row in existing_rows if row.get("title_key")}
    existing_urls = {row["url_key"] for row in existing_rows if row.get("url_key")}
    existing_by_title = {clean_title(row["title_key"]).lower(): row for row in existing_rows if row.get("title_key")}
    existing_by_url = {row["url_key"]: row for row in existing_rows if row.get("url_key")}

    inserted = 0
    for item in items:
        title_key = clean_title(item["title"]).lower()
        url_key = item["url"]
        if title_key in existing_titles or url_key in existing_urls:
            existing = existing_by_title.get(title_key) or existing_by_url.get(url_key)
            if existing:
                update_existing_record(conn, lead_cols, existing, item)
            continue
        payload = build_insert_payload(lead_cols=lead_cols, source=source, item=item)
        if not payload:
            continue
        insert_lead(conn, payload, lead_cols, source["source_id"])
        existing_titles.add(title_key)
        existing_urls.add(url_key)
        inserted += 1

    update_source_status(
        conn,
        source_id=source["source_id"],
        source_cols=source_cols,
        records_found=len(items),
        status="success",
    )
    conn.commit()
    return CrawlResult(status="success", records_found=len(items), records_promoted=inserted)


def main() -> None:
    conn = get_conn()
    try:
        source_cols = get_table_columns(conn, "registry_sources")
        lead_cols = get_table_columns(conn, "opportunity_leads")
        sources = load_sources(conn, source_cols)
        for source in sources:
            try:
                result = run_source_crawl(conn, source, source_cols=source_cols, lead_cols=lead_cols)
            except Exception as exc:
                conn.rollback()
                update_source_status(
                    conn,
                    source_id=source["source_id"],
                    source_cols=source_cols,
                    records_found=0,
                    status="error",
                )
                conn.commit()
                print(source["source_id"], "error", 0, 0, str(exc)[:160])
            else:
                print(source["source_id"], result.status, result.records_found, result.records_promoted)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
