"""Bounded fingerprint retrieval for the DRJTBC professional-services pilot."""
import hashlib
import time
from urllib.parse import urlsplit

import requests

MAX_BYTES = 10 * 1024 * 1024


def fingerprint(url):
    try:
        parsed = urlsplit(url)
        supported = (parsed.scheme == 'https' and parsed.hostname in ('www.drjtbc.org', 'drjtbc.org')
            and parsed.port in (None, 443) and not parsed.username and not parsed.password
            and parsed.path.startswith('/wp-content/uploads/')
            and parsed.path.lower().endswith('.pdf'))
    except ValueError:
        supported = False
    if not supported:
        return {'state': 'unavailable', 'reason': 'Outside supported PDF scope'}
    try:
        started = time.monotonic()
        with requests.get(url, stream=True, allow_redirects=False, timeout=(5, 10)) as response:
            if response.status_code != 200:
                return {'state': 'unavailable', 'reason': 'Document could not be retrieved'}
            digest = hashlib.sha256()
            prefix = b''
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES or time.monotonic() - started > 30:
                    return {'state': 'unavailable', 'reason': 'Document exceeds check limits'}
                prefix = (prefix + chunk)[:1024]
                digest.update(chunk)
            if not prefix.lstrip().startswith(b'%PDF-'):
                return {'state': 'unavailable', 'reason': 'Response was not a PDF'}
            return {'state': 'ok', 'sha256': digest.hexdigest()}
    except (requests.RequestException, ValueError):
        return {'state': 'unavailable', 'reason': 'Document could not be retrieved'}


def inspect_documents(records):
    cache = {}
    for record in records:
        documents = [{'title': 'Request for proposals', 'url': record.get('official_url', '')}]
        documents += record.get('published_addenda') or []
        checks = []
        seen = set()
        for document in documents:
            url = document['url']
            if url in seen:
                continue
            seen.add(url)
            if url not in cache:
                cache[url] = (fingerprint(url) if len(cache) < 24 else
                              {'state': 'unavailable', 'reason': 'Source check limit reached'})
            checks.append({**document, **cache[url]})
        record['document_checks'] = checks
