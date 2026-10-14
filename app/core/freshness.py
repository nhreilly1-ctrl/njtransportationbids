"""Discovery and material source changes are independent of refresh time."""
from datetime import datetime
import re

FIELDS = {'title': 'Title changed', 'due_date_raw': 'Deadline changed',
          'anticipated_date_raw': 'Forecast changed', 'source_status': 'Agency status changed',
          'official_url': 'Official link changed', 'notice_excerpt': 'Notice text changed',
          'procurement_milestones': 'Meeting or question deadline changed',
          'published_addenda': 'Published addenda list changed'}


# Material changes are kept as a short newest-first history, not just the latest
# one: a deadline change followed days later by a text edit must not erase the
# deadline change. History cannot be reconstructed after the fact, so it is
# bounded rather than deferred.
HISTORY_LIMIT = 10


def record_change(record, labels, at):
    """Mark a material change, keeping both the latest-change fields and history."""
    record['materially_changed_at'] = at
    record['change_labels'] = labels
    history = record.get('change_history') or []
    record['change_history'] = ([{'at': at, 'labels': list(labels)}] + history)[:HISTORY_LIMIT]
    record.setdefault('change_history_since', at)


def changes_since(record, since):
    """Changes recorded after ``since``, and whether that list is known to be complete.

    Incomplete means the record changed in a period history does not cover: before
    tracking began for this record, or older than the retained window. ``since``
    must be timezone-aware; anything else is treated as unknown, not as zero.
    """
    since_ts = _timestamp(since)
    history = record.get('change_history') or []
    if since_ts is None:
        return [], False
    entries = [e for e in history if (_timestamp(e.get('at')) or 0) > since_ts]
    started = _timestamp(record.get('change_history_since'))
    oldest = _timestamp(history[-1].get('at')) if history else None
    truncated = len(history) >= HISTORY_LIMIT and oldest is not None and oldest > since_ts
    untracked_change = (_timestamp(record.get('materially_changed_at')) or 0) > since_ts and not history
    complete = (started is not None and started <= since_ts and not truncated
                and not untracked_change)
    return entries, complete


def stamp_refresh(record, previous, checked_at):
    from app.core.document_changes import reconcile_documents
    document_changed = reconcile_documents(record, previous, checked_at)
    record['last_checked_at'] = checked_at
    record['first_seen_at'] = previous.get('first_seen_at') if previous is not None else checked_at
    record['materially_changed_at'] = previous.get('materially_changed_at') if previous else None
    record['change_labels'] = previous.get('change_labels', []) if previous else []
    record['change_history'] = list(previous.get('change_history') or []) if previous else []
    record['change_history_since'] = (previous or {}).get('change_history_since') or checked_at
    if previous is not None:
        normalize = lambda value: re.sub(r'\s+', ' ', str(value or '')).strip()
        labels = [label for field, label in FIELDS.items()
                  if normalize(previous.get(field)) != normalize(record.get(field))]
        if previous.get('source_inactive'):
            labels.append('Returned to agency listing')
        if document_changed:
            labels.append('Document changed; review required')
        if labels:
            record_change(record, labels, checked_at)


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
