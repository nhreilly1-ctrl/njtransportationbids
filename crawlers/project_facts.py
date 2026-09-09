"""Small, source-specific PDF pilot. Retrieval failure clears current facts."""
import hashlib
import io
from urllib.parse import urlparse
from pypdf import PdfReader
from app.core.project_facts import parse_njdot_facts


def collect_njdot_facts(record, get, checked_at):
    url = record.get('official_url', '')
    pack = {'state': 'unavailable', 'url': url, 'checked_at': checked_at,
            'contract': record.get('contract_number'), 'items': []}
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'dot.nj.gov'
            or not parsed.path.lower().endswith('.pdf')):
        return pack
    try:
        response = get(url)
        if response is None or not response.content.startswith(b'%PDF') or len(response.content) > 10_000_000:
            return pack
        reader = PdfReader(io.BytesIO(response.content))
        text = reader.pages[0].extract_text()
        items = parse_njdot_facts(text or '', pack['contract'])
        pack.update(state='ok', items=items, sha256=hashlib.sha256(response.content).hexdigest())
    except Exception:
        return pack
    return pack
