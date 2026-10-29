"""Bounded checks of agency-linked bid advertisements and addenda."""
import hashlib
import io
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from pypdf import PdfReader
from app.core.bid_documents import choose_bid_document, document_identity_matches, parse_bid_deadline, publication_date

MAX_DOCUMENTS = 6
MAX_BYTES = 10_000_000


def _document_link(url, title, **metadata):
    match = re.search(r'\b(?:addendum|amendment)\s*(?:no\.?|#)?\s*(\d+)\b', title, re.I)
    return dict(url=url, title=title, kind='addendum' if re.search(r'\b(?:addendum|amendment)\b', title, re.I) else 'advertisement',
                **({'sequence': int(match[1])} if match else {}), **metadata)


def _allowed_pdf(url, record):
    try:
        parsed = urlsplit(url)
        source = urlsplit(record.get('source_url', ''))
        allowed = {source.hostname}
        if record.get('source_id') == 'state-njtransit':
            allowed.add('content.njtransit.com')
        return (parsed.scheme == 'https' and parsed.hostname in allowed
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and parsed.path.lower().endswith('.pdf'))
    except ValueError:
        return False


def collect_bid_document_review(record, get, checked_at):
    url = record.get('official_url') or ''
    result = dict(state='unavailable', listing_url=url, contract=record.get('contract_number'),
                  checked_at=checked_at, documents=[])
    if record.get('is_planned') or record.get('scope_excluded'):
        return None
    facts = record.get('project_facts') or {}
    if (record.get('source_id') == 'state-njdot-construction' and facts.get('state') == 'ok'
            and facts.get('url') == url and facts.get('contract') == record.get('contract_number')):
        candidate = dict(url=url, title='Current bid advertisement', kind='advertisement',
                         state='ok', identity_verified=bool(facts.get('bid_date')),
                         sha256=facts.get('sha256'), checked_at=checked_at,
                         deadline=facts.get('bid_date'))
        result['documents'] = [candidate]
        selected, reason = choose_bid_document(result['documents'])
        result.update(state='resolved' if selected else 'needs_review', reason=reason)
        return result
    documents = []
    if _allowed_pdf(url, record):
        documents.append(_document_link(url, 'Current bid advertisement'))
    elif _allowed_pdf(record.get('deadline_evidence_url') or '', record):
        documents.append(_document_link(record['deadline_evidence_url'], 'Current bid advertisement'))
    elif record.get('source_id') == 'state-njta':
        response = get(url)
        if response is None:
            return result
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.select('a[href]'):
            title = link.get_text(' ', strip=True)
            target = urljoin(url, link['href'])
            if (_allowed_pdf(target, record)
                    and re.search(r'newspaper\s+ad|advertis|bid\s+notice|notice\s+to|addendum|amendment', title, re.I)):
                documents.append(_document_link(target, title))
        if not documents:
            result.update(state='no_document', reason='No accessible bid advertisement is linked on this listing.')
            return result
    else:
        return None
    for item in record.get('published_addenda') or []:
        if _allowed_pdf(item.get('url', ''), record):
            documents.append(_document_link(item['url'], item.get('title', 'Addendum'),
                                            **({'published_date': item['date']} if item.get('date') else {})))
    unique = {item['url']: item for item in documents}
    for index, candidate in enumerate(unique.values()):
        candidate.update(state='unavailable', checked_at=checked_at)
        result['documents'].append(candidate)
        if index >= MAX_DOCUMENTS:
            continue
        try:
            response = get(candidate['url'])
            if response is None or len(response.content) > MAX_BYTES or not response.content.startswith(b'%PDF'):
                continue
            reader = PdfReader(io.BytesIO(response.content))
            pages = [page.extract_text() or '' for page in reader.pages[:4]]
            identity = document_identity_matches(' '.join(pages), record.get('contract_number'))
            candidate.update(state='ok', sha256=hashlib.sha256(response.content).hexdigest(),
                             identity_verified=identity,
                             deadline=parse_bid_deadline(pages, record.get('contract_number')))
            published = publication_date(pages)
            if published:
                candidate['published_date'] = published
        except Exception:
            continue
    selected, reason = choose_bid_document(result['documents'])
    result.update(state='resolved' if selected else 'needs_review', reason=reason)
    if result['documents'] and all(item['state'] == 'unavailable' for item in result['documents']):
        result['state'] = 'unavailable'
    return result


def inspect_bid_documents(records, get, checked_at):
    for record in records:
        review = collect_bid_document_review(record, get, checked_at)
        if review is not None:
            record['bid_document_review'] = review
