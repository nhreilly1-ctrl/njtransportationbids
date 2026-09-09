"""NJDOT notice facts: published values, never bidder eligibility decisions."""
import re
from datetime import datetime, timedelta, timezone

LABELS = {'estimate': 'Published estimate range', 'completion': 'Estimated completion',
          'work_types': 'Published eligible work types'}


def parse_njdot_facts(text, contract):
    text = re.sub(r'\s+', ' ', text)
    if not contract or not re.search(r'\bContract\s+No\.?\s*' + re.escape(contract) + r'(?![\w-])', text, re.I):
        return []
    patterns = {
        'estimate': r'Estimated Range\s*\(for Information Purpose Only\)\s*:\s*(Range between\s+\$[\d,]+\s+to\s+\$[\d,]+)',
        'completion': r'Estimated Completion Date\s*:\s*(\d{1,2}/\d{1,2}/\d{4})',
        'work_types': r'Contractors Prequalified in one of these Work Types are eligible to bid this project\s*:\s*([\d]+(?:\s*(?:,|or|and)\s*\d+)*)\b',
    }
    facts = []
    for kind, pattern in patterns.items():
        matches = list(re.finditer(pattern, text, re.I))
        if len(matches) == 1:
            facts.append({'kind': kind, 'value': matches[0].group(1),
                          'evidence': matches[0].group(), 'page': 1})
    return facts


def project_facts_display(record, now=None):
    pack = record.get('project_facts')
    if record.get('source_id') != 'state-njdot-construction' or not pack:
        return None
    result = {'items': [], 'needs_review': True, 'checked_at': pack.get('checked_at', '')[:10]}
    try:
        checked = datetime.fromisoformat(pack['checked_at'].replace('Z', '+00:00'))
        fresh = timedelta(0) <= (now or datetime.now(timezone.utc)) - checked <= timedelta(hours=48)
    except (KeyError, ValueError, TypeError):
        fresh = False
    if (not fresh or pack.get('state') != 'ok' or not pack.get('sha256')
            or pack.get('url') != record.get('official_url')
            or pack.get('contract') != record.get('contract_number')):
        return result
    result['needs_review'] = False
    result['url'] = pack['url']
    result['items'] = [dict(item, label=LABELS[item['kind']]) for item in pack.get('items', [])
                       if item.get('kind') in LABELS and item.get('evidence')]
    return result
