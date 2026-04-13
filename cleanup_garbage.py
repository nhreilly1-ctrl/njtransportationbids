"""
cleanup_garbage.py
Run once to retroactively reject garbage leads and unpublish
any live opportunities that came from them.

    python cleanup_garbage.py
"""
from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(__file__)
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != os.path.abspath(SCRIPT_DIR)]
sys.modules["logging"] = importlib.import_module("logging")
sys.path.insert(0, SCRIPT_DIR)

from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.filters import should_reject_lead


def get_table_columns(db, table_name: str) -> set[str]:
    rows = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    ).fetchall()
    return {row[0] for row in rows}


def parse_due_value(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text_value = str(value).strip()
    if not text_value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(text_value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def run_cleanup():
    db = SessionLocal()
    try:
        lead_columns = get_table_columns(db, "opportunity_leads")
        live_columns = get_table_columns(db, "opportunities_live")
        public_columns = get_table_columns(db, "opportunities")

        if not lead_columns:
            raise RuntimeError("Table opportunity_leads was not found in the connected database.")

        title_column = "notice_title" if "notice_title" in lead_columns else "title"
        due_column = "due_at" if "due_at" in lead_columns else "due_date"
        created_column = "created_at"
        status_column = "lead_status" if "lead_status" in lead_columns else "status"
        decision_column = "promotion_decision" if "promotion_decision" in lead_columns else None
        notes_column = "notes" if "notes" in lead_columns else "admin_notes"
        promoted_flag_column = "promoted_flag" if "promoted_flag" in lead_columns else None

        leads = db.execute(
            text(
                """
                SELECT
                    lead_id,
                    {title_column} AS lead_title,
                    {due_column} AS lead_due,
                    {created_column} AS lead_created
                FROM opportunity_leads
                WHERE COALESCE({status_column}, '') != 'rejected'
                """.format(
                    title_column=title_column,
                    due_column=due_column,
                    created_column=created_column,
                    status_column=status_column,
                )
            )
        ).mappings().all()

        rejected_count = 0
        unpublished_count = 0

        for lead in leads:
            parsed_due = parse_due_value(lead["lead_due"])
            reject, reason = should_reject_lead(
                title=lead["lead_title"],
                due_at=parsed_due,
                created_at=lead["lead_created"],
            )

            if reject:
                update_parts = [f"{status_column} = 'rejected'"]
                if decision_column:
                    update_parts.append(f"{decision_column} = 'Reject'")
                update_parts.append(f"{notes_column} = COALESCE({notes_column}, '') || :note")

                db.execute(
                    text(
                        """
                        UPDATE opportunity_leads
                        SET
                            {update_assignments}
                        WHERE lead_id = :lead_id
                        """.format(update_assignments=", ".join(update_parts))
                    ),
                    {
                        "lead_id": lead["lead_id"],
                        "note": f"\n[AUTO] {reason}",
                    },
                )
                rejected_count += 1

                deleted_count = 0

                if live_columns:
                    deleted = db.execute(
                        text(
                            """
                            DELETE FROM opportunities_live
                            WHERE lead_id = :lead_id
                            """
                        ),
                        {"lead_id": lead["lead_id"]},
                    )
                    deleted_count += deleted.rowcount or 0

                if public_columns:
                    deleted = db.execute(
                        text(
                            """
                            DELETE FROM opportunities
                            WHERE opportunity_id = :opportunity_id
                            """
                        ),
                        {"opportunity_id": f"opp-{lead['lead_id']}"},
                    )
                    deleted_count += deleted.rowcount or 0

                if deleted_count and promoted_flag_column:
                    db.execute(
                        text(
                            """
                            UPDATE opportunity_leads
                            SET {promoted_flag_column} = FALSE
                            WHERE lead_id = :lead_id
                            """.format(promoted_flag_column=promoted_flag_column)
                        ),
                        {"lead_id": lead["lead_id"]},
                    )

                unpublished_count += deleted_count

        db.commit()
        print(f"Done. Rejected {rejected_count} leads, unpublished {unpublished_count} live opportunities.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    run_cleanup()
