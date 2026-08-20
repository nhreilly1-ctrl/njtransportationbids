"""Generate an auditable county taxonomy CSV from the canonical notice feed."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.core.geography import classify_geography


FIELDS = (
    "record_id",
    "county_raw",
    "canonical_counties",
    "coverage_scope",
    "region_raw",
    "confidence",
    "evidence",
)


def raw_value(record: dict) -> str:
    if "county" not in record or record["county"] is None:
        return "<NULL>"
    value = str(record["county"])
    if value == "":
        return "<EMPTY>"
    if value.isspace():
        return "<WS>"
    return value


def build_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        result = classify_geography(record)
        rows.append(
            {
                "record_id": record.get("id", ""),
                "county_raw": raw_value(record),
                "canonical_counties": "|".join(result["counties"]),
                "coverage_scope": result["coverage_scope"],
                "region_raw": result["region_raw"] or "",
                "confidence": result["geography_confidence"],
                "evidence": result["geography_evidence"],
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/notices/notices.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/county_taxonomy_analysis.csv"))
    args = parser.parse_args()

    records = json.loads(args.input.read_text(encoding="utf-8"))
    rows = build_rows(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    conflicts = sum("R-03" in row["evidence"] for row in rows)
    resolved = sum(bool(row["canonical_counties"]) for row in rows)
    print(f"Wrote {len(rows)} rows to {args.output}")
    print(f"R-03 conflicts: {conflicts}")
    print(f"County-resolved: {resolved}")


if __name__ == "__main__":
    main()

