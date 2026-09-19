"""Disclose corroborated NJDOT PDF/listing disagreement; never replace a date."""
from datetime import date, datetime, timedelta, timezone


def document_deadline_warning(record, listing_date, now=None):
    pack = record.get('project_facts') or {}
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
    if not timedelta(0) <= age <= timedelta(hours=48) or pdf_date == current_date:
        return None
    return {'listing_date': current_date.isoformat(), 'pdf_date': pdf_date.isoformat(),
            'url': pack['url'], 'checked_at': pack['checked_at'][:10]}
