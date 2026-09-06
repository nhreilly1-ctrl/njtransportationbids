"""Discovery and material source changes are independent of refresh time."""
from datetime import datetime
import re

FIELDS = {'title': 'Title changed', 'due_date_raw': 'Deadline changed',
          'anticipated_date_raw': 'Forecast changed', 'source_status': 'Agency status changed',
          'official_url': 'Official link changed', 'notice_excerpt': 'Notice text changed'}


def stamp_refresh(record, previous, checked_at):
    record['last_checked_at'] = checked_at
    record['first_seen_at'] = previous.get('first_seen_at') if previous is not None else checked_at
    record['materially_changed_at'] = previous.get('materially_changed_at') if previous else None
    record['change_labels'] = previous.get('change_labels', []) if previous else []
    if previous is not None:
        normalize = lambda value: re.sub(r'\s+', ' ', str(value or '')).strip()
        labels = [label for field, label in FIELDS.items()
                  if normalize(previous.get(field)) != normalize(record.get(field))]
        if previous.get('source_inactive'):
            labels.append('Returned to agency listing')
        if labels:
            record['materially_changed_at'] = checked_at
            record['change_labels'] = labels


def feed_order(value):
    return value if value in ('newest', 'updated', 'closing') else 'newest'


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def newest_first(records, mode='newest'):
    field = 'materially_changed_at' if mode == 'updated' else 'first_seen_at'
    return sorted(records, key=lambda r: (_timestamp(r.get(field)) is None,
        -(_timestamp(r.get(field)) or 0), str(r.get('title', '')).casefold(), str(r.get('id', ''))))


def freshness_groups(records, mode='newest', limit=None):
    field = 'materially_changed_at' if mode == 'updated' else 'first_seen_at'
    ordered = newest_first(records, mode)[:limit]
    known = [r for r in ordered if _timestamp(r.get(field)) is not None]
    unknown = [r for r in ordered if _timestamp(r.get(field)) is None]
    headings = ('Recently updated', 'No recorded changes') if mode == 'updated' else (
        'Newly listed', 'Discovery date not recorded')
    return [dict(heading=heading, urgency='normal', opportunities=rows)
            for heading, rows in zip(headings, (known, unknown)) if rows]
