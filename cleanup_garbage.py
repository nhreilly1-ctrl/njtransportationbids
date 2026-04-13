"""
cleanup_garbage.py
Run once to retroactively reject garbage leads and unpublish
any live opportunities that came from them.

    python cleanup_garbage.py
"""
from __future__ import annotations
import sys, os
import importlib

SCRIPT_DIR = os.path.dirname(__file__)
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != os.path.abspath(SCRIPT_DIR)]
sys.modules["logging"] = importlib.import_module("logging")
sys.path.insert(0, SCRIPT_DIR)

from app.core.db import SessionLocal
from app.core.filters import should_reject_lead
from app.models.opportunity_leads import OpportunityLead
from app.models.opportunities_live import OpportunityLive


def run_cleanup():
    db = SessionLocal()
    try:
        leads = db.query(OpportunityLead).filter(
            OpportunityLead.lead_status != 'rejected'
        ).all()

        rejected_count = 0
        unpublished_count = 0

        for lead in leads:
            reject, reason = should_reject_lead(
                title=lead.notice_title,
                due_at=lead.due_at,
                created_at=lead.created_at,
            )
            if reject:
                lead.lead_status = 'rejected'
                lead.promotion_decision = 'Reject'
                lead.notes = (lead.notes or '') + f'\n[AUTO] {reason}'
                rejected_count += 1

                live = db.query(OpportunityLive).filter(
                    OpportunityLive.lead_id == lead.lead_id
                ).first()
                if live:
                    db.delete(live)
                    lead.promoted_flag = False
                    unpublished_count += 1

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
