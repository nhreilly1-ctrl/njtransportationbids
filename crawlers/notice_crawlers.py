"""
notice_crawlers.py
------------------
Parser implementations for all NJ public notice sources.

Each parser:
  - Receives a source dict from notice_sources.py
  - Fetches and parses HTML
  - Returns list of raw notice dicts ready for enrichment

Output notice dict shape:
  {
    id, title, notice_excerpt, source_id, source_name, source_tier,
    source_url, official_url, county, entity_type,
    notice_type, notice_subtype,
    due_date_raw, contract_number,
    access_type, platform, paywalled,
    crawled_at, raw_html_snippet
  }
"""

import re, hashlib, time, logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# ── HTTP helpers ──────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NJTransportationBids-crawler/1.0; "
        "+https://www.njtransportationbids.com)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def _get(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        log.warning(f"GET {url} failed: {e}")
        return None

def _soup(html, parser="html.parser"):
    return BeautifulSoup(html, parser)

def _now():
    return datetime.now(timezone.utc).isoformat()

def _make_id(source_id, title, url=""):
    raw = f"{source_id}:{title}:{url}"
    return "notice-" + hashlib.md5(raw.encode()).hexdigest()[:12]

def _clean(text):
    """Strip excess whitespace, normalize dashes."""
    if not text: return ""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*[-–—]\s*', ' — ', text)
    return text

def _excerpt(text, chars=400):
    """Return cleaned excerpt up to chars, ending at a word boundary."""
    text = _clean(text)
    if len(text) <= chars:
        return text
    cut = text[:chars].rsplit(' ', 1)[0]
    return cut + "..."

# Transportation keyword filter — applied to municipal/county generic crawls
TRANSPORT_KW = [
    "roadway", "road improvement", "road resurfacing", "road repair",
    "bridge", "culvert", "drainage", "pavement", "paving", "milling",
    "overlay", "curb", "sidewalk", "intersection", "signal",
    "guardrail", "guide rail", "highway", "transportation",
    "engineering services", "construction inspection", "cei",
    "professional services", "rfp", "rfq", "design services",
    "structural", "geotechnical", "survey", "environmental",
    "traffic", "streetscape", "resurfacing", "reconstruction",
    "maintenance contract", "joc", "job order contract",
    "notice to bidders", "notice to contractors", "legal notice",
    "bid solicitation", "bid opening", "sealed bids",
]

def _is_transport_relevant(title, body=""):
    text = (title + " " + body).lower()
    return any(kw in text for kw in TRANSPORT_KW)


# ── NJDOT Construction ────────────────────────────────────────────────────────

def parse_njdot_construction(source):
    """
    NJDOT current advertised projects page.
    The page renders project data in an HTML table with columns:
    Contract No | Description | Counties | Let Date | Download
    """
    records = []
    r = _get(source["url"])
    if not r: return records

    soup = _soup(r.text)
    # Find all table rows — skip header
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all(["td","th"])
            if len(cells) < 3: continue

            contract_no  = _clean(cells[0].get_text())
            description  = _clean(cells[1].get_text())
            counties     = _clean(cells[2].get_text()) if len(cells) > 2 else "Statewide"
            let_date     = _clean(cells[3].get_text()) if len(cells) > 3 else ""

            # Get download link
            link = cells[-1].find("a") if cells else None
            official_url = urljoin(source["url"], link["href"]) if link and link.get("href") else source["url"]

            if not description or len(description) < 10: continue

            title = description
            if contract_no:
                title = f"Contract {contract_no} — {description}"

            records.append({
                "id":             _make_id(source["id"], title),
                "title":          title,
                "notice_excerpt": f"NJDOT construction contract. {description}. Counties: {counties}.",
                "source_id":      source["id"],
                "source_name":    source["name"],
                "source_tier":    source["source_tier"],
                "source_url":     source["url"],
                "official_url":   official_url,
                "county":         counties or "Statewide",
                "entity_type":    source["entity_type"],
                "notice_type":    "construction",
                "notice_subtype": "construction",
                "due_date_raw":   let_date,
                "contract_number":contract_no,
                "access_type":    source["access_type"],
                "platform":       source["platform"],
                "paywalled":      False,
                "crawled_at":     _now(),
            })

    # Also crawl planned ads page
    if source.get("planned_url"):
        records += _parse_njdot_planned(source)

    log.info(f"NJDOT construction: {len(records)} records")
    return records


def _parse_njdot_planned(source):
    """Parse planned advertisement page for forward-looking notices."""
    records = []
    r = _get(source["planned_url"])
    if not r: return records

    soup = _soup(r.text)
    for row in soup.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 2: continue
        desc      = _clean(cells[0].get_text())
        counties  = _clean(cells[1].get_text()) if len(cells) > 1 else ""
        est_date  = _clean(cells[2].get_text()) if len(cells) > 2 else ""
        if not desc or len(desc) < 8: continue
        records.append({
            "id":             _make_id(source["id"], "planned:" + desc),
            "title":          f"[Planned] {desc}",
            "notice_excerpt": f"Planned NJDOT advertisement. Est. advertisement: {est_date}. Counties: {counties}.",
            "source_id":      source["id"],
            "source_name":    source["name"],
            "source_tier":    source["source_tier"],
            "source_url":     source["planned_url"],
            "official_url":   source["planned_url"],
            "county":         counties or "Statewide",
            "entity_type":    source["entity_type"],
            "notice_type":    "construction",
            "notice_subtype": "construction",
            "due_date_raw":   est_date,
            "contract_number":"",
            "access_type":    source["access_type"],
            "platform":       source["platform"],
            "paywalled":      False,
            "is_planned":     True,
            "crawled_at":     _now(),
        })
    return records


# ── NJDOT Professional Services ───────────────────────────────────────────────

def parse_njdot_profserv(source):
    """
    NJDOT professional services solicitations table.
    Columns: TP # | Due Date | Type | Discipline | Project Description | Status
    """
    records = []
    r = _get(source["url"])
    if not r: return records

    soup = _soup(r.text)
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all(["td","th"])
            if len(cells) < 4: continue

            tp_num      = _clean(cells[0].get_text())
            due_date    = _clean(cells[1].get_text())
            discipline  = _clean(cells[2].get_text()) if len(cells) > 2 else ""
            description = _clean(cells[3].get_text()) if len(cells) > 3 else ""
            status      = _clean(cells[-1].get_text()) if cells else ""

            # Parse discipline codes like "B-1 Level A H-1 Level B"
            codes = re.findall(r'[A-Z]-\d+', discipline + " " + description)
            code_str = " · ".join(codes) if codes else discipline

            if not description or len(description) < 8: continue

            title = f"NJDOT {tp_num} — {description}" if tp_num else description
            excerpt = (
                f"NJDOT professional services solicitation. "
                f"Prequalification required: {code_str}. "
                f"Due: {due_date}. Status: {status}."
            )

            records.append({
                "id":             _make_id(source["id"], title),
                "title":          title,
                "notice_excerpt": excerpt,
                "source_id":      source["id"],
                "source_name":    source["name"],
                "source_tier":    source["source_tier"],
                "source_url":     source["url"],
                "official_url":   source["url"],
                "county":         "Statewide",
                "entity_type":    source["entity_type"],
                "notice_type":    "professional_services",
                "notice_subtype": "professional_services",
                "due_date_raw":   due_date,
                "contract_number":tp_num,
                "prequal_codes":  codes,
                "access_type":    source["access_type"],
                "platform":       source["platform"],
                "paywalled":      False,
                "crawled_at":     _now(),
            })

    log.info(f"NJDOT prof services: {len(records)} records")
    return records


# ── NJTA ──────────────────────────────────────────────────────────────────────

def parse_njta(source):
    """
    NJ Turnpike Authority current solicitations page.
    Lists construction contracts (T-series, P-series) and
    engineering professional services (OPS numbers) together.
    """
    records = []
    r = _get(source["url"])
    if not r: return records

    soup = _soup(r.text)

    # NJTA page uses structured sections with h3/h4 headers and ul/table lists
    # Strategy: find all links with context
    for item in soup.find_all(["li", "tr", "p"]):
        text = _clean(item.get_text())
        if len(text) < 15: continue

        link = item.find("a")
        official_url = urljoin(source["url"], link["href"]) if link and link.get("href") else source["url"]

        # Extract contract number
        contract_match = re.search(
            r'\b([TP]\d{3}\.\d{3,4}|[TP]-?\d{3,4}|OPS No\. [A-Z]\d+|Order [A-Z]?\d+)\b',
            text, re.I
        )
        contract_no = contract_match.group(0) if contract_match else ""

        # Extract date
        date_match = re.search(
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
            r'|\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            text, re.I
        )
        due_date = date_match.group(0) if date_match else ""

        # Determine type
        is_profserv = any(kw in text.lower() for kw in [
            "professional services", "engineering services", "ops no", "order for professional",
            "design services", "inspection services", "t4", "p4", "p3"
        ])
        notice_type = "professional_services" if is_profserv else "construction"

        # Skip non-transportation items
        if not _is_transport_relevant(text): continue

        title = text[:200]
        records.append({
            "id":             _make_id(source["id"], title),
            "title":          title,
            "notice_excerpt": text[:400],
            "source_id":      source["id"],
            "source_name":    source["name"],
            "source_tier":    source["source_tier"],
            "source_url":     source["url"],
            "official_url":   official_url,
            "county":         "Statewide",
            "entity_type":    source["entity_type"],
            "notice_type":    notice_type,
            "notice_subtype": notice_type,
            "due_date_raw":   due_date,
            "contract_number":contract_no,
            "access_type":    source["access_type"],
            "platform":       source["platform"],
            "paywalled":      False,
            "crawled_at":     _now(),
        })

    log.info(f"NJTA: {len(records)} records")
    return records


# ── DRJTBC ────────────────────────────────────────────────────────────────────

def parse_drjtbc(source):
    """
    DRJTBC construction notices and professional services current procurements.
    Both pages have similar structure: project title, document links, dates.
    """
    records = []
    r = _get(source["url"])
    if not r: return records

    soup = _soup(r.text)
    is_profserv = "profserv" in source["id"] or "professional" in source["url"]

    # Find project blocks — typically div or article elements with h3/h4 titles
    for block in soup.find_all(["article","div","section"], class_=re.compile(r'project|procurement|listing|item', re.I)):
        title_el = block.find(["h2","h3","h4","strong"])
        if not title_el: continue
        title = _clean(title_el.get_text())
        if len(title) < 10: continue

        body = _clean(block.get_text())
        link = block.find("a", href=re.compile(r'\.(pdf|doc|htm)', re.I))
        official_url = urljoin(source["url"], link["href"]) if link and link.get("href") else source["url"]

        date_match = re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s*\d{4}\b', body, re.I)
        due_date = date_match.group(0) if date_match else ""

        contract_match = re.search(r'\b(?:Contract|DB|C)-?\s*[A-Z0-9]{3,10}\b', body, re.I)
        contract_no = contract_match.group(0) if contract_match else ""

        notice_type = "professional_services" if is_profserv else "construction"

        records.append({
            "id":             _make_id(source["id"], title),
            "title":          title,
            "notice_excerpt": _excerpt(body),
            "source_id":      source["id"],
            "source_name":    source["name"],
            "source_tier":    source["source_tier"],
            "source_url":     source["url"],
            "official_url":   official_url,
            "county":         source["county"],
            "entity_type":    source["entity_type"],
            "notice_type":    notice_type,
            "notice_subtype": notice_type,
            "due_date_raw":   due_date,
            "contract_number":contract_no,
            "access_type":    source["access_type"],
            "platform":       source["platform"],
            "paywalled":      False,
            "crawled_at":     _now(),
        })

    # Fallback: parse paragraphs if no blocks found
    if not records:
        for p in soup.find_all("p"):
            text = _clean(p.get_text())
            if len(text) < 30 or not _is_transport_relevant(text): continue
            link = p.find("a")
            official_url = urljoin(source["url"], link["href"]) if link and link.get("href") else source["url"]
            records.append({
                "id":             _make_id(source["id"], text[:80]),
                "title":          text[:150],
                "notice_excerpt": _excerpt(text),
                "source_id":      source["id"],
                "source_name":    source["name"],
                "source_tier":    source["source_tier"],
                "source_url":     source["url"],
                "official_url":   official_url,
                "county":         source["county"],
                "entity_type":    source["entity_type"],
                "notice_type":    "professional_services" if is_profserv else "construction",
                "notice_subtype": "professional_services" if is_profserv else "construction",
                "due_date_raw":   "",
                "contract_number":"",
                "access_type":    source["access_type"],
                "platform":       source["platform"],
                "paywalled":      False,
                "crawled_at":     _now(),
            })

    log.info(f"DRJTBC {source['id']}: {len(records)} records")
    return records


# ── NJ DOS Legal Notices ──────────────────────────────────────────────────────

def parse_nj_dos_legal(source):
    """
    NJ Department of State legal notices page.
    Since Mar 2026 this is the canonical statewide legal notice repository.
    Filter aggressively for transportation/construction content.
    """
    records = []
    r = _get(source["url"])
    if not r: return records

    soup = _soup(r.text)

    for item in soup.find_all(["li","p","div"], class_=re.compile(r'notice|item|entry', re.I)):
        text = _clean(item.get_text())
        if len(text) < 20: continue
        if not _is_transport_relevant(text): continue

        link = item.find("a")
        official_url = urljoin(source["url"], link["href"]) if link and link.get("href") else source["url"]
        title = _clean(link.get_text()) if link else text[:150]

        date_match = re.search(
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s*\d{4}\b'
            r'|\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            text, re.I
        )
        due_date = date_match.group(0) if date_match else ""

        # Classify notice subtype
        is_prof = any(k in text.lower() for k in ["rfp","rfq","professional services","engineering","consultant"])
        is_constr = any(k in text.lower() for k in ["notice to bidders","notice to contractors","sealed bids","roadway","bridge","paving"])
        if is_prof:
            ntype, nsub = "public_notice", "professional_services"
        elif is_constr:
            ntype, nsub = "public_notice", "construction"
        else:
            ntype, nsub = "public_notice", None

        records.append({
            "id":             _make_id(source["id"], title),
            "title":          title or text[:150],
            "notice_excerpt": _excerpt(text),
            "source_id":      source["id"],
            "source_name":    source["name"],
            "source_tier":    source["source_tier"],
            "source_url":     source["url"],
            "official_url":   official_url,
            "county":         "Statewide",
            "entity_type":    source["entity_type"],
            "notice_type":    ntype,
            "notice_subtype": nsub,
            "due_date_raw":   due_date,
            "contract_number":"",
            "access_type":    "Public access",
            "platform":       "NJDOS legal notices portal",
            "paywalled":      False,
            "crawled_at":     _now(),
        })

    log.info(f"NJ DOS legal notices: {len(records)} records")
    return records


# ── SoS Directory (Tier 3 seed) ───────────────────────────────────────────────

def parse_sos_directory(source):
    """
    Crawl the Secretary of State statewide legal notices directory.
    Extracts all submitted entity URLs — feeds the Tier 3 municipal crawler.
    Returns a list of {entity_name, legal_notices_url} dicts, NOT notice records.
    Call this separately from notice_runner.py to seed Tier 3.
    """
    r = _get(source["url"])
    if not r: return []

    soup = _soup(r.text)
    entities = []

    # Page lists entities with their legal notice page URLs
    for row in soup.find_all(["tr","li","div"]):
        link = row.find("a", href=re.compile(r'http', re.I))
        if not link: continue
        href = link.get("href","")
        if not href or "nj.gov/state" in href: continue  # skip self-links
        name = _clean(row.get_text())[:100]
        entities.append({
            "entity_name": name,
            "legal_notices_url": href,
            "discovered_at": _now(),
        })

    log.info(f"SoS directory: {len(entities)} entity URLs discovered")
    return entities


# ── Generic HTML List (county/municipal fallback) ─────────────────────────────

def parse_generic_html_list(source):
    """
    Fallback parser for county and municipal sites.
    Finds bid/notice links and extracts title, date, URL.
    Applies transportation keyword filter.
    """
    records = []
    r = _get(source["url"])
    if not r: return records

    soup = _soup(r.text)
    seen = set()

    # Strategy 1: find anchor tags that look like bid postings
    bid_link_patterns = re.compile(
        r'bid|notice|rfp|rfq|solicitation|procurement|advertisement|award|contract',
        re.I
    )

    for a in soup.find_all("a", href=True):
        text = _clean(a.get_text())
        href = a.get("href","")
        if not text or len(text) < 10: continue
        if not bid_link_patterns.search(text) and not bid_link_patterns.search(href): continue
        if not _is_transport_relevant(text): continue
        if text in seen: continue
        seen.add(text)

        official_url = urljoin(source["url"], href)

        # Try to get date from surrounding context
        parent = a.find_parent(["li","tr","div","p"])
        context = _clean(parent.get_text()) if parent else text
        date_match = re.search(
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s*\d{4}\b'
            r'|\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            context, re.I
        )
        due_date = date_match.group(0) if date_match else ""

        contract_match = re.search(r'\bBid\s+No\.?\s*[\w-]+|\bRFP\s+[\d-]+|\bBid\s+#\s*[\w-]+', context, re.I)
        contract_no = contract_match.group(0) if contract_match else ""

        # Classify
        is_prof = any(k in text.lower() for k in ["rfp","rfq","professional","engineering","consultant","design"])
        ntype = "professional_services" if is_prof else "construction"

        records.append({
            "id":             _make_id(source["id"], text),
            "title":          text[:250],
            "notice_excerpt": _excerpt(context),
            "source_id":      source["id"],
            "source_name":    source["name"],
            "source_tier":    source["source_tier"],
            "source_url":     source["url"],
            "official_url":   official_url,
            "county":         source.get("county",""),
            "entity_type":    source["entity_type"],
            "notice_type":    ntype,
            "notice_subtype": ntype,
            "due_date_raw":   due_date,
            "contract_number":contract_no,
            "access_type":    source.get("access_type","Unknown"),
            "platform":       source.get("platform","Agency website"),
            "paywalled":      False,
            "crawled_at":     _now(),
        })

    # Strategy 2: look for legal notice sections added post-PL2025-c72
    legal_section = soup.find(id=re.compile(r'legal.notice|notice.bid', re.I))
    if legal_section:
        for p in legal_section.find_all("p"):
            text = _clean(p.get_text())
            if len(text) < 30 or not _is_transport_relevant(text): continue
            if text in seen: continue
            seen.add(text)
            records.append({
                "id":             _make_id(source["id"], text[:80]),
                "title":          text[:200],
                "notice_excerpt": _excerpt(text),
                "source_id":      source["id"],
                "source_name":    source["name"],
                "source_tier":    source["source_tier"],
                "source_url":     source["url"],
                "official_url":   source["url"],
                "county":         source.get("county",""),
                "entity_type":    source["entity_type"],
                "notice_type":    "public_notice",
                "notice_subtype": None,
                "due_date_raw":   "",
                "contract_number":"",
                "access_type":    source.get("access_type","Unknown"),
                "platform":       source.get("platform","Agency website"),
                "paywalled":      False,
                "crawled_at":     _now(),
            })

    log.info(f"{source['name']}: {len(records)} records")
    return records


# ── Essex County dedicated portal ─────────────────────────────────────────────

def parse_essex_county(source):
    """Essex has a dedicated procurement portal with structured JSON-like data."""
    records = []

    # Essex legal notices page is more useful than their procurement portal
    legal_url = source.get("legal_url", source["url"])
    r = _get(legal_url)
    if not r:
        r = _get(source["url"])
    if not r: return records

    soup = _soup(r.text)
    for item in soup.find_all(["li","div","article"]):
        link = item.find("a", href=True)
        if not link: continue
        text = _clean(link.get_text())
        if len(text) < 10: continue
        if not _is_transport_relevant(text): continue

        href = link.get("href","")
        official_url = urljoin(legal_url, href)
        context = _clean(item.get_text())

        date_match = re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', context)
        due_date = date_match.group(0) if date_match else ""

        is_prof = "rfp" in text.lower() or "rfq" in text.lower()
        ntype = "professional_services" if is_prof else "construction"

        records.append({
            "id":             _make_id(source["id"], text),
            "title":          text[:250],
            "notice_excerpt": _excerpt(context),
            "source_id":      source["id"],
            "source_name":    source["name"],
            "source_tier":    source["source_tier"],
            "source_url":     legal_url,
            "official_url":   official_url,
            "county":         "Essex",
            "entity_type":    source["entity_type"],
            "notice_type":    ntype,
            "notice_subtype": ntype,
            "due_date_raw":   due_date,
            "contract_number":"",
            "access_type":    source["access_type"],
            "platform":       source["platform"],
            "paywalled":      False,
            "crawled_at":     _now(),
        })

    log.info(f"Essex County: {len(records)} records")
    return records


# ── Camden County dedicated portal ────────────────────────────────────────────

def parse_camden_county(source):
    """Camden has procurements.camdencounty.com — structured listing."""
    records = []
    r = _get(source["url"])
    if not r: return records

    soup = _soup(r.text)
    for item in soup.find_all(["article","div","li"], class_=re.compile(r'procurement|bid|item', re.I)):
        title_el = item.find(["h2","h3","h4","a","strong"])
        if not title_el: continue
        title = _clean(title_el.get_text())
        if len(title) < 10 or not _is_transport_relevant(title): continue

        link = item.find("a", href=True)
        official_url = urljoin(source["url"], link["href"]) if link else source["url"]
        context = _clean(item.get_text())

        date_match = re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s*\d{4}\b', context, re.I)
        due_date = date_match.group(0) if date_match else ""

        is_prof = "rfp" in title.lower() or "rfq" in title.lower() or "professional" in title.lower()
        ntype = "professional_services" if is_prof else "construction"

        records.append({
            "id":             _make_id(source["id"], title),
            "title":          title,
            "notice_excerpt": _excerpt(context),
            "source_id":      source["id"],
            "source_name":    source["name"],
            "source_tier":    source["source_tier"],
            "source_url":     source["url"],
            "official_url":   official_url,
            "county":         "Camden",
            "entity_type":    source["entity_type"],
            "notice_type":    ntype,
            "notice_subtype": ntype,
            "due_date_raw":   due_date,
            "contract_number":"",
            "access_type":    source["access_type"],
            "platform":       source["platform"],
            "paywalled":      False,
            "crawled_at":     _now(),
        })

    if not records:
        records = parse_generic_html_list(source)

    log.info(f"Camden County: {len(records)} records")
    return records


# ── Monmouth County ───────────────────────────────────────────────────────────

def parse_monmouth_county(source):
    """Monmouth has a searchable portal at pol.co.monmouth.nj.us."""
    records = []

    # The Monmouth portal requires POSTing a search — use generic fallback
    # but try the open bids list first
    open_bids_url = "https://pol.co.monmouth.nj.us/County/tblBids.aspx?Status=Open"
    r = _get(open_bids_url)
    if not r:
        return parse_generic_html_list(source)

    soup = _soup(r.text)
    for row in soup.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 3: continue

        req_id    = _clean(cells[0].get_text())
        due_date  = _clean(cells[1].get_text())
        title     = _clean(cells[2].get_text())

        if not title or not _is_transport_relevant(title): continue

        link = row.find("a", href=True)
        official_url = urljoin(open_bids_url, link["href"]) if link else source["url"]

        is_prof = "rfp" in title.lower() or "rfq" in title.lower()
        ntype = "professional_services" if is_prof else "construction"

        records.append({
            "id":             _make_id(source["id"], title),
            "title":          f"Monmouth County — {title}",
            "notice_excerpt": f"Monmouth County bid solicitation. Request ID: {req_id}. Due: {due_date}. {title}",
            "source_id":      source["id"],
            "source_name":    source["name"],
            "source_tier":    source["source_tier"],
            "source_url":     open_bids_url,
            "official_url":   official_url,
            "county":         "Monmouth",
            "entity_type":    source["entity_type"],
            "notice_type":    ntype,
            "notice_subtype": ntype,
            "due_date_raw":   due_date,
            "contract_number":req_id,
            "access_type":    source["access_type"],
            "platform":       source["platform"],
            "paywalled":      False,
            "crawled_at":     _now(),
        })

    log.info(f"Monmouth County: {len(records)} records")
    return records


# ── Gloucester County ─────────────────────────────────────────────────────────

def parse_gloucester_county(source):
    """Gloucester uses .aspx bid listing with bidID params."""
    records = []
    r = _get(source["url"])
    if not r: return records

    soup = _soup(r.text)
    for row in soup.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 2: continue
        title = _clean(cells[0].get_text() if cells else "")
        if not title or not _is_transport_relevant(title): continue

        link = row.find("a", href=re.compile(r'bidID', re.I))
        official_url = urljoin(source["url"], link["href"]) if link else source["url"]
        date_cell = _clean(cells[1].get_text()) if len(cells) > 1 else ""

        is_prof = "rfp" in title.lower() or "rfq" in title.lower()
        ntype = "professional_services" if is_prof else "construction"

        records.append({
            "id":             _make_id(source["id"], title),
            "title":          f"Gloucester County — {title}",
            "notice_excerpt": _excerpt(_clean(row.get_text())),
            "source_id":      source["id"],
            "source_name":    source["name"],
            "source_tier":    source["source_tier"],
            "source_url":     source["url"],
            "official_url":   official_url,
            "county":         "Gloucester",
            "entity_type":    source["entity_type"],
            "notice_type":    ntype,
            "notice_subtype": ntype,
            "due_date_raw":   date_cell,
            "contract_number":"",
            "access_type":    source["access_type"],
            "platform":       source["platform"],
            "paywalled":      False,
            "crawled_at":     _now(),
        })

    log.info(f"Gloucester County: {len(records)} records")
    return records


# ── Municipal Tier 3 — seeded from SoS directory ─────────────────────────────

def parse_municipal_from_sos(entity_url, entity_name, county=""):
    """
    Called by the Tier 3 runner after SoS directory provides URLs.
    Generic parser for municipal legal notice pages under PL2025-c72.
    """
    source_id = "sos-" + hashlib.md5(entity_url.encode()).hexdigest()[:8]
    synthetic_source = {
        "id":          source_id,
        "name":        entity_name,
        "source_tier": "municipal",
        "url":         entity_url,
        "access_type": "Public access",
        "platform":    "Municipal website",
        "entity_type": "Municipality",
        "county":      county,
    }
    return parse_generic_html_list(synthetic_source)


# ── Dispatcher ────────────────────────────────────────────────────────────────

PARSER_MAP = {
    "njdot_construction":   parse_njdot_construction,
    "njdot_profserv":       parse_njdot_profserv,
    "njta":                 parse_njta,
    "njtransit":            parse_generic_html_list,   # NJ TRANSIT calendar
    "drjtbc":               parse_drjtbc,
    "nj_dos_legal":         parse_nj_dos_legal,
    "sos_directory":        parse_sos_directory,
    "essex_county":         parse_essex_county,
    "camden_county":        parse_camden_county,
    "monmouth_county":      parse_monmouth_county,
    "gloucester_county":    parse_gloucester_county,
    "generic_html_list":    parse_generic_html_list,
    "bidnet":               parse_generic_html_list,
    "questcdn":             parse_generic_html_list,
}

def crawl_source(source, delay=1.5):
    """Crawl a single source. Returns list of notice dicts."""
    parser_name = source.get("parser","generic_html_list")
    parser_fn   = PARSER_MAP.get(parser_name, parse_generic_html_list)
    try:
        records = parser_fn(source)
        time.sleep(delay)   # polite delay between requests
        return records
    except Exception as e:
        log.error(f"Error crawling {source['id']}: {e}")
        return []
