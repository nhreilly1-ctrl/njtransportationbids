"""Measure which return-visit features the current notice data can truthfully support.

Run from the repository root:

    python analyze_return_use_coverage.py [path/to/notices.json]

"Code" means at least one record from that agency group carries the field at all,
so some parser or enrichment path emits it. "Live" means the field is populated on
records currently open or upcoming. A feature is only as good as its live column:
code support with an empty live column cannot back a user-facing promise.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.bid_readiness import _track  # noqa: E402  (agency grouping, reused)

LIVE = ("open", "upcoming")
TRACK_LABELS = {
    "njdot": "NJDOT", "njta": "NJ Turnpike Auth.", "panynj": "Port Authority",
    "njtransit": "NJ TRANSIT", "bistate": "DRPA / DRJTBC", "local": "Counties & towns",
    "state_other": "Other state",
}
FIELDS = [
    ("Discovery date", "first_seen_at"),
    ("Recorded change", "materially_changed_at"),
    ("Meeting / question dates", "procurement_milestones"),
    ("Addenda list", "published_addenda"),
    ("Document fingerprints", "document_checks"),
    ("Forecast window", "anticipated_date_raw"),
    ("Published size facts", "project_facts"),
]


def is_live(record):
    return (record.get("status") in LIVE and not record.get("source_inactive")
            and not record.get("noise_flagged"))


def norm_contract(value):
    value = re.sub(r"[‐-―−]", "-", str(value or ""))
    return re.sub(r"\s*-\s*", "-", value).strip().upper()


def coverage(records):
    groups = defaultdict(list)
    for record in records:
        groups[_track(str(record.get("source_id") or ""))].append(record)

    lines = ["| Agency group | Live | " + " | ".join(h for h, _ in FIELDS) + " |",
             "|---|---:|" + "---:|" * len(FIELDS)]
    totals = Counter()
    for key, label in TRACK_LABELS.items():
        rows = groups.get(key, [])
        if not rows:
            continue
        live = [r for r in rows if is_live(r)]
        cells = []
        for _, field in FIELDS:
            count = sum(1 for r in live if r.get(field))
            totals[field] += count
            cells.append(str(count) if any(field in r for r in rows) else "no code")
        totals["live"] += len(live)
        lines.append(f"| {label} | {len(live)} | " + " | ".join(cells) + " |")
    lines.append(f"| **All** | **{totals['live']}** | "
                 + " | ".join(f"**{totals[f]}**" for _, f in FIELDS) + " |")
    return "\n".join(lines)


def identity_risks(records):
    """Where the title-hashed ID scheme would make a saved item or a 'new' badge lie."""
    by_key = defaultdict(list)
    for record in records:
        contract = norm_contract(record.get("contract_number"))
        if contract:
            by_key[(record.get("source_id"), contract)].append(record)
    successor_pairs = false_new = 0
    for rows in by_key.values():
        active = [r for r in rows if not r.get("source_inactive")]
        if active and any(r.get("source_inactive") for r in rows):
            successor_pairs += 1
            false_new += any(r.get("first_seen_at") for r in active)
    live = [r for r in records if is_live(r)]
    changed = [r for r in live if r.get("materially_changed_at")]
    return {
        "retired->active pairs sharing source + contract number (title edit = new ID)": successor_pairs,
        "  of which the active record has a discovery date (would badge as new)": false_new,
        "live records with no contract number (nothing to re-link a saved item by)":
            sum(1 for r in live if not norm_contract(r.get("contract_number"))),
        "live records with a recorded material change": len(changed),
        "latest-change labels on those records (earlier changes are overwritten)":
            dict(Counter(l for r in changed for l in (r.get("change_labels") or [])).most_common()),
    }


def main(path):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    print(f"Source: {path} - {len(records)} records, {sum(1 for r in records if is_live(r))} live\n")
    print(coverage(records))
    print()
    for label, value in identity_risks(records).items():
        print(f"- {label}: {value}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "notices" / "notices.json"))
