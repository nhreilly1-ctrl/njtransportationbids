from __future__ import annotations


def verify_lead(notice_url: str | None, official_url: str | None) -> str:
    if official_url:
        return 'Verified'
    if notice_url:
        return 'Partial'
    return 'Unknown'
