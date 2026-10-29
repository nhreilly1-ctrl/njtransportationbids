"""Evidence and ordering for closing dates in official bid advertisements."""
import re
from datetime import datetime, timezone

MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
DATE = rf'(?:{MONTH}\s+\d{{1,2}},?\s+20\d{{2}}|\d{{1,2}}/\d{{1,2}}/\d{{2}}(?:\d{{2}})?|20\d{{2}}-\d{{2}}-\d{{2}})'
TIME = r'\d{1,2}:\d{2}\s*(?:AM|PM)(?:\s*(?:EST|EDT|ET|Eastern Time))?'


def publication_date(pages):
    text = re.sub(r'\s+', ' ', ' '.join(pages))
    values = re.findall(rf'\b(?:Project Advertisement Date|Publication Date|Date Issued|Issue Date)\s*:\s*({DATE})', text, re.I)
    dates = set()
    for raw in values:
        for fmt in ('%B %d, %Y', '%B %d %Y', '%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d'):
            try:
                dates.add(datetime.strptime(raw, fmt).date().isoformat())
                break
            except ValueError:
                pass
    return next(iter(dates)) if len(dates) == 1 else None


def document_identity_matches(text, contract):
    if not contract:
        return False
    contract = re.sub(r'^(?:IFB|RFP|RFQ|BID|CONTRACT)\s*(?:NO\.?|NUMBER|#)?\s*', '', contract, flags=re.I)
    parts = re.findall(r'[A-Za-z0-9]+', contract)
    pattern = r'[\s.\-–—]*'.join(re.escape(part) for part in parts)
    return bool(parts and re.search(rf'(?<!\w){pattern}(?!\w)', text, re.I))


def parse_bid_deadline(pages, contract):
    """Read explicitly identified submission dates; reject meeting and question dates."""
    whole = ' '.join(pages)
    if not document_identity_matches(whole, contract):
        return None
    found = []
    for page, source in enumerate(pages, 1):
        text = re.sub(r'\s+', ' ', source)
        text = re.sub(r'\b([ap])\.?\s*m\.', lambda m: m[1].upper() + 'M', text, flags=re.I)
        labelled = list(re.finditer(
            rf'\b(?:Project Bid Date|Bid Due Date|Proposal Due Date|Closing Date|'
            rf'Date for receipt of (?:bids|proposals))\s*(?::|is)?\s*({DATE})', text, re.I))
        contexts = [(m.group(), m.group(1)) for m in labelled]
        if not labelled:
            for sentence in re.split(r'(?<=[.!?])\s+', text):
                if re.search(r'pre[ -]?bid|conference|site visit|questions|prequalification', sentence, re.I):
                    continue
                if not re.search(r'\b(?:bids?|proposals?|responses|submission)\b.{0,200}'
                                 r'\b(?:received|due|submitted|accepted)\b', sentence, re.I):
                    continue
                # A single submission clause may also state an opening time. Only
                # select its date when there is exactly one distinct date.
                dates = re.findall(DATE, sentence, re.I)
                if len(set(dates)) == 1:
                    contexts.append((sentence, dates[0]))
        for evidence, raw in contexts:
            parsed = None
            for fmt in ('%B %d, %Y', '%B %d %Y', '%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d'):
                try:
                    parsed = datetime.strptime(raw, fmt).date()
                    break
                except ValueError:
                    pass
            if parsed is None:
                continue
            times = re.findall(TIME, evidence, re.I)
            # Do not turn a date-only label into an invented submission time.
            time_text = times[0] if len(set(t.upper() for t in times)) == 1 else ''
            closing_raw = parsed.isoformat() if not time_text else f'{parsed.strftime("%B %d, %Y")} at {time_text}'
            found.append({'date': parsed.isoformat(), 'raw': closing_raw,
                          'evidence': evidence.strip(), 'page': page})
    dates = {item['date'] for item in found}
    if len(dates) != 1:
        return None
    precise = [item for item in found if ' at ' in item['raw']]
    if len({item['raw'].lower() for item in precise}) > 1:
        return None
    return (precise or found)[0]


def choose_bid_document(documents):
    """Order published versions, never crawl order or the latest closing date."""
    if not documents:
        return None, 'No linked bid advertisement has been checked.'
    if all(d.get('published_date') for d in documents):
        try:
            for item in documents:
                datetime.strptime(item['published_date'], '%Y-%m-%d')
        except (TypeError, ValueError):
            return None, 'Document publication dates need review.'
        newest_date = max(d['published_date'] for d in documents)
        candidates = [d for d in documents if d['published_date'] == newest_date]
    else:
        addenda = [d for d in documents if d.get('kind') == 'addendum']
        candidates = addenda or documents
    if all(type(d.get('sequence')) is int for d in candidates):
        newest = max(d['sequence'] for d in candidates)
        candidates = [d for d in candidates if d['sequence'] == newest]
    elif all(d.get('published_date') for d in candidates):
        newest = max(d['published_date'] for d in candidates)
        candidates = [d for d in candidates if d['published_date'] == newest]
    elif len(candidates) > 1:
        return None, 'Document order is unresolved; review the linked advertisements and addenda.'
    if len({d.get('url') for d in candidates}) != 1:
        return None, 'Several documents have the same published version; review their deadlines.'
    selected = candidates[0]
    if (selected.get('state') != 'ok' or not selected.get('sha256')
            or not selected.get('identity_verified') or not (selected.get('deadline') or {}).get('evidence')):
        return None, 'The latest linked document needs a deadline review.'
    return selected, ''


def controlling_document(record):
    """Return only evidence tied to the currently linked solicitation identity."""
    pack = record.get('bid_document_review') or {}
    if pack:
        if pack.get('contract') != record.get('contract_number') or pack.get('listing_url') != record.get('official_url'):
            return None
        selected, _ = choose_bid_document(pack.get('documents') or [])
        return selected
    # Existing NJDOT first-page checks already have exact contract, URL, hash
    # and quoted bid-date evidence. They are usable until their current link changes.
    pack = record.get('project_facts') or {}
    if pack.get('state') != 'ok' or not pack.get('bid_date'):
        pack = pack.get('previous_date_check') or {}
    bid = pack.get('bid_date') or {}
    if (record.get('source_id') != 'state-njdot-construction'
            or pack.get('state') != 'ok' or not pack.get('sha256')
            or not record.get('contract_number') or pack.get('contract') != record.get('contract_number')
            or pack.get('url') != record.get('official_url')
            or not bid.get('evidence') or bid.get('page') != 1):
        return None
    try:
        checked = datetime.fromisoformat(pack['checked_at'].replace('Z', '+00:00'))
        if checked > datetime.now(timezone.utc):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return {'url': pack['url'], 'sha256': pack['sha256'], 'checked_at': pack['checked_at'],
            'state': 'ok', 'identity_verified': True, 'kind': 'advertisement', 'deadline': bid}


def retain_bid_document_review(record, previous):
    """An outage cannot restore a superseded listing date or an older PDF."""
    if (record.get('source_id') != previous.get('source_id')
            or record.get('contract_number') != previous.get('contract_number')
            or record.get('official_url') != previous.get('official_url')):
        return
    current = record.get('bid_document_review') or {}
    old = previous.get('bid_document_review') or {}
    prior_document = controlling_document(previous)
    if current.get('state') == 'unavailable' and prior_document:
        if not old:
            old = dict(state='resolved', contract=previous.get('contract_number'),
                       listing_url=previous.get('official_url'),
                       checked_at=prior_document.get('checked_at'), documents=[prior_document])
        if current.get('documents') and {d['url'] for d in current['documents']} != {d['url'] for d in old.get('documents', [])}:
            return
        record['bid_document_review'] = {**old, 'recheck_failed_at': current.get('checked_at'),
                                         'recheck_note': 'Latest check failed; showing the last verified bid document.'}
