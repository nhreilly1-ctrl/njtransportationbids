"""Conservative timing notes, never replacement dates or lifecycle decisions."""

import re
from datetime import date


MONTHS = {name: index for index, name in enumerate(
    ('january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'), 1)}


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
