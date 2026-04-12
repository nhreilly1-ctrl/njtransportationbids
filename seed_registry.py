from __future__ import annotations

import sys
from pathlib import Path

from app.core.db import SessionLocal
from app.services.import_registry import import_registry_csv, import_registry_workbook


USAGE = "Usage: python scripts/seed_registry.py path/to/registry_sources.csv|registry_workbook.xlsx [sheet_name]"


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(USAGE)

    input_path = Path(sys.argv[1])
    sheet_name = sys.argv[2] if len(sys.argv) > 2 else 'Master Registry'

    db = SessionLocal()
    try:
        suffix = input_path.suffix.lower()
        if suffix == '.csv':
            count = import_registry_csv(db, str(input_path))
        elif suffix in {'.xlsx', '.xlsm'}:
            count = import_registry_workbook(db, str(input_path), sheet_name=sheet_name)
        else:
            raise SystemExit(f'Unsupported file type: {suffix}. {USAGE}')
        print(f'Imported {count} source rows from {input_path.name}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
