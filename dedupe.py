from __future__ import annotations

from hashlib import sha256

from app.core.scoring import normalize_text


def compute_duplicate_hash(agency: str | None, title: str | None, due_date: str | None, official_url: str | None) -> str:
    normalized = "|".join([
        normalize_text(agency),
        normalize_text(title),
        normalize_text(due_date),
        normalize_text(official_url),
    ])
    return sha256(normalized.encode("utf-8")).hexdigest()
