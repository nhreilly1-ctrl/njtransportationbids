"""Reviewed agency orientation, never a source of normalized notice fields."""

REVIEWED_ON = "2026-09-07"


def preparation_for(record):
    source = record.get("source_id")
    kind = record.get("record_type") or record.get("notice_type")
    if kind not in ("construction", "professional_services"):
        return None
    title = text = url = None
    if source == "state-njdot-construction" and kind == "construction":
        title = "NJDOT construction: check your qualification first"
        text = ("Start with the current DC-74A application instructions, financial statements "
                "and payment requirements. Confirm your approved work classification and the "
                "project's special provisions before preparing a bid. Application submission "
                "does not establish approval.")
        url = "https://nj.gov/transportation/business/procurement/ConstrServ/prequalrequire.shtm"
    elif source in ("state-njdot-profserv", "state-njdot-profserv-upcoming") and kind == "professional_services":
        title = "NJDOT consultants: allow time for approval"
        text = ("Prime consultants need prequalification; professional subconsultants need "
                "cost-basis approval. NJDOT publishes minimum package submission lead times "
                "of five business days for prequalification and twenty days for cost-basis "
                "approval. Submission is not approval. Check the solicitation's disciplines "
                "and proposal delivery instructions separately.")
        url = "https://www.nj.gov/transportation/business/procurement/ProfServ/prequal.shtm"
    elif source == "state-njta":
        title = "NJTA: verify the applicable qualification"
        if kind == "construction":
            text = ("Construction classification has a one-year validity period under the "
                    "agency's published rule. Check your current approval and classification "
                    "limits, then follow this solicitation's security and submission instructions.")
        else:
            text = ("Consultant PSPQ validity depends on the financial statements: up to 24 months "
                    "with audited or CPA-reviewed statements, or 12 months with compiled or "
                    "internally prepared statements. Confirm current approval and the EOI's "
                    "required profile codes; do not assume every approval lasts two years.")
        url = "https://www.njta.gov/document/notice-of-proposed-substantial-changes-upon-adoption-to-proposed-amendments/"
    elif source == "county-ocean":
        title = "Ocean County: start with the OpenGov project"
        text = ("The county directs current bids to OpenGov; its older procurement system "
                "contains award results. Open this project's instructions, attachments, "
                "questions and addenda to confirm how to submit. Construction forms are "
                "not automatically requirements for a professional-services proposal.")
        url = "https://webhost2.co.ocean.nj.us/ocbidportal.nsf/home"
    elif source == "county-morris":
        title = "Morris County: confirm delivery before bid day"
        text = ("The county's published purchasing guide describes identified, sealed formal "
                "bids received before the solicitation deadline. This guide uses legacy wording: "
                "confirm delivery, signatures and opening time in the current project package. "
                "Do not assume a document-download portal also accepts submissions.")
        url = "https://www.morriscountynj.gov/files/sharedassets/public/departments/purchasing/doingbusiness-w-morriscty.pdf"
    if not title:
        return None
    return {"title": title, "text": text, "url": url, "reviewed_on": REVIEWED_ON,
            "scope": "Agency preparation guidance, not a complete submission checklist"}
