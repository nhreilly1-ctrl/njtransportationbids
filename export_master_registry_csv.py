from __future__ import annotations

import sys
from pathlib import Path

from app.services.import_registry import export_master_registry_to_csv


USAGE = "Usage: python scripts/export_master_registry_csv.py path/to/registry_workbook.xlsx output/master_registry_export.csv [sheet_name]"


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(USAGE)

    workbook_path = Path(sys.argv[1])
    output_csv = Path(sys.argv[2])
    sheet_name = sys.argv[3] if len(sys.argv) > 3 else 'Master Registry'

    count = export_master_registry_to_csv(str(workbook_path), str(output_csv), sheet_name=sheet_name)
    print(f'Exported {count} registry rows from {workbook_path.name} to {output_csv}')


if __name__ == '__main__':
    main()
