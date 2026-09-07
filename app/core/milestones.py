"""Source-published procurement steps, independent of the bid deadline."""
from app.core.deadlines import normalize_deadline, deadline_is_past


LABELS = {'preproposal_meeting': 'Pre-proposal meeting',
          'questions_due': 'Question deadline'}


def milestone_display(record):
    items = []
    for item in record.get('procurement_milestones') or []:
        if item.get('kind') not in LABELS or not item.get('raw'):
            continue
        normalized = normalize_deadline({'due_date_raw': item['raw']})
        items.append({**item, 'label': LABELS[item['kind']],
                      'display': normalized['deadline_display'],
                      'date': normalized.get('due_date_parsed'),
                      'past': deadline_is_past(normalized)})
    return items


def schedule_indicator(record):
    """A compact route to the published schedule, never an automatic alert."""
    if record.get('status') != 'open':
        return ''
    items = record.get('milestones_display') or []
    future = sorted((m for m in items if m.get('date') and not m['past']),
                    key=lambda m: m['date'])
    if future:
        next_item = future[0]
        text = next_item['label'] + ': ' + next_item['display']
    elif any(not m.get('date') for m in items):
        text = 'Meeting/question timing needs confirmation'
    elif items:
        text = 'Published meeting/question dates have passed'
    else:
        text = ''
    if record.get('published_addenda'):
        text = (text + ' - ' if text else '') + 'Review agency addenda'
    return text
