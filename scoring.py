from __future__ import annotations

TRANSPORT_TERMS = [
    'road', 'street', 'bridge', 'paving', 'resurfacing', 'traffic signal',
    'intersection', 'transit', 'rail', 'transportation', 'mobility', 'drainage',
    'sidewalk', 'engineering', 'inspection', 'municipal aid', 'airport', 'station'
]

NEGATIVE_TERMS = [
    'janitorial', 'office supplies', 'furniture', 'cafeteria', 'holiday lighting'
]



def transport_score(text: str) -> int:
    lower = (text or '').lower()
    score = 0
    for term in TRANSPORT_TERMS:
        if term in lower:
            score += 8
    for term in NEGATIVE_TERMS:
        if term in lower:
            score -= 10
    return max(0, min(score, 100))



def confidence_score(*, notice_title: str | None, official_url: str | None, due_at_present: bool) -> int:
    score = 30
    if notice_title:
        score += 20
    if official_url:
        score += 30
    if due_at_present:
        score += 20
    return min(score, 100)
