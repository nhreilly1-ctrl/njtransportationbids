"""Disclose NJDOT PDF/listing disagreement; never replace a date."""
from datetime import date, datetime, timedelta, timezone


def document_deadline_warning(record, listing_date, now=None):
    pack = record.get('project_facts') or {}
    previous_check = pack.get('state') != 'ok' or not pack.get('bid_date')
    if previous_check:
        pack = pack.get('previous_date_check') or {}
    bid = pack.get('bid_date') or {}
    if (record.get('source_id') != 'state-njdot-construction'
            or pack.get('state') != 'ok' or not pack.get('sha256')
            or not record.get('contract_number')
            or pack.get('contract') != record.get('contract_number')
            or pack.get('url') != record.get('official_url')
            or not bid.get('evidence') or bid.get('page') != 1):
        return None
    try:
        checked = datetime.fromisoformat(pack['checked_at'].replace('Z', '+00:00'))
        age = (now or datetime.now(timezone.utc)) - checked
        pdf_date = date.fromisoformat(bid['date'])
        current_date = date.fromisoformat(listing_date)
    except (KeyError, TypeError, ValueError):
        return None
    if age < timedelta(0) or pdf_date == current_date:
        return None
    return {'listing_date': current_date.isoformat(), 'pdf_date': pdf_date.isoformat(),
            'url': pack['url'], 'checked_at': pack['checked_at'][:10],
            'stale': previous_check or age > timedelta(hours=48)}


def retain_document_date_check(record, previous):
    """A failed refresh is not proof a previously observed conflict disappeared."""
    if (record.get('source_id') != 'state-njdot-construction'
            or record.get('id') != previous.get('id')
            or record.get('contract_number') != previous.get('contract_number')
            or record.get('official_url') != previous.get('official_url')):
        return
    current = record.get('project_facts')
    if not isinstance(current, dict) or (current.get('state') == 'ok' and current.get('bid_date')):
        return
    old = previous.get('project_facts') or {}
    if old.get('state') != 'ok' or not old.get('bid_date'):
        old = old.get('previous_date_check') or {}
    if old.get('state') == 'ok' and old.get('bid_date'):
        current['previous_date_check'] = {key: old.get(key) for key in
            ('state', 'contract', 'url', 'sha256', 'checked_at', 'bid_date')}
