"""Conservative timing notes, never replacement dates or lifecycle decisions."""

import re
import calendar
from datetime import date


MONTHS = {name: index for index, name in enumerate(
    ('january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'), 1)}


def forecast_window_end(record: dict) -> date | None:
    """Bound only supported advertisement windows, never bid deadlines."""
    text = str(record.get('anticipated_date_raw') or record.get('due_date_raw') or '').strip().lower()
    match = re.fullmatch(r'([a-z]+)\s+(20\d{2})', text)
    if match and match[1] in MONTHS:
        year, month = int(match[2]), MONTHS[match[1]]
        return date(year, month, calendar.monthrange(year, month)[1])
    if record.get('source_id') == 'state-njdot-profserv-upcoming':
        # NJDOT publishes quarter-based seasons. Winter year labels are ambiguous.
        match = re.fullmatch(r'(spring|summer|fall)\s+(20\d{2}|\d{2})(?:\s*\(may/june\))?', text)
        if match:
            year = int(match[2])
            year += 2000 if year < 100 else 0
            month = 6 if '(may/june)' in text else {'spring': 6, 'summer': 9, 'fall': 12}[match[1]]
            return date(year, month, calendar.monthrange(year, month)[1])
    if record.get('source_id') == 'state-njtransit':
        try:
            published = date.fromisoformat(record.get('forecast_publication_date', ''))
        except (ValueError, TypeError):
            return None
        parts = text.split('/')
        if all(part in MONTHS for part in parts) and 1 <= len(parts) <= 2:
            months = [MONTHS[part] for part in parts]
            # Do not guess a year across a year boundary or a retrospective window.
            if months == sorted(months) and months[0] >= published.month:
                month = months[-1]
                return date(published.year, month, calendar.monthrange(published.year, month)[1])
    return None


def forecast_state(record: dict, today: date) -> dict:
    end = forecast_window_end(record)
    elapsed = end is not None and end < today
    return {
        'forecast_window_end': end.isoformat() if end else None,
        'forecast_window_elapsed': elapsed,
        'forecast_timing_note': (
            'Expected window has passed; advertisement not confirmed.' if elapsed
            else 'Agency forecast, not a confirmed advertisement or bid date.' if end
            else forecast_timing_note(record.get('due_date_raw', ''), today)
        ),
    }


def forecast_timing_note(raw: str, today: date) -> str:
    text = str(raw or '').strip().lower()
    years = re.findall(r'\b(?:19|20)\d{2}\b', text)
    if not years:
        if re.search(r'\b\d{2}\b', text):
            return 'Timing not confirmed; verify the abbreviated forecast year with the agency.'
        return 'Timing not confirmed; year not stated in the published window.'
    # Only unambiguous full month/year windows have a known month boundary.
    month = re.fullmatch(r'([a-z]+)\s+(\d{4})', text)
    if month and month[1] in MONTHS:
        if (int(month[2]), MONTHS[month[1]]) < (today.year, today.month):
            return 'Published forecast window has passed; confirm revised timing with the agency.'
    season = re.fullmatch(r'(spring|summer|fall|autumn)\s+(\d{4})', text)
    if season and int(season[2]) < today.year:
        return 'Published forecast window has passed; confirm revised timing with the agency.'
    return 'Agency forecast, not a confirmed advertisement or bid date.'
