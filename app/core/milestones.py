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
                      'past': deadline_is_past(normalized)})
    return items
