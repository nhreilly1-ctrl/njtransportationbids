"""Human-reviewed project instructions, gated by the reviewed document versions."""

from datetime import datetime, timedelta, timezone

RFP = "https://www.drjtbc.org/wp-content/uploads/C-753ARFPFinal.pdf"
ADDENDUM = "https://www.drjtbc.org/wp-content/uploads/C-753AAddendumNo.01.pdf"
REVIEWED_HASHES = {
    RFP: "3862498819481fe07becb410eff2fe3093ba0bc13d48a7bc4be237935fa342f6",
    ADDENDUM: "dddc6926d15527729f37d522377de55a301e13f179de68e871844d6edbf9293d",
}


def checklist_for(record, now=None):
    if (record.get("id") != "notice-e849321e5763"
            or record.get("source_id") != "state-drjtbc-profserv"
            or record.get("contract_number") != "C-753A"
            or record.get("official_url") != RFP
            or record.get("status") != "open"
            or record.get("source_inactive")):
        return None
    now = now or datetime.now(timezone.utc)
    pack = {"reviewed_on": "2026-09-08", "url": ADDENDUM, "steps": [],
            "needs_review": True}
    addenda = {d.get("url") for d in record.get("published_addenda", [])}
    checks = {d.get("url"): d for d in record.get("document_checks", [])}
    if addenda != {ADDENDUM} or set(checks) != set(REVIEWED_HASHES):
        return pack
    for url, digest in REVIEWED_HASHES.items():
        check = checks[url]
        if check.get("state") != "ok" or check.get("sha256") != digest:
            return pack
        try:
            checked = datetime.fromisoformat(check["last_successful_check"].replace("Z", "+00:00"))
            if checked.tzinfo is None or not timedelta(0) <= now - checked <= timedelta(hours=48):
                return pack
        except (KeyError, TypeError, ValueError):
            return pack
    pack["needs_review"] = False
    pack["steps"] = [
        {"text": "Email the proposal to the Project Manager, copying the Chief Engineer and Assistant Chief Engineer. Confirm recipients in the RFP.", "page": "AD1-5"},
        {"text": "Deliver six hardcopies of the Technical Proposal and Fee Proposal in separate sealed envelopes to the Scudder Falls Administration Building. This is in addition to email submission.", "page": "AD1-5"},
        {"text": "Sign Addendum No. 1 and attach its acknowledgment page to the proposal.", "page": "AD1-1"},
    ]
    return pack
