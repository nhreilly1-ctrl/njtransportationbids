# Reviewed project submission checks

Pilot: DRJTBC C-753A, reviewed 2026-09-08. Selected instructions only, not a
certification of a complete proposal. No inferred deadline or agency-wide rule.

Source: https://www.drjtbc.org/wp-content/uploads/C-753AAddendumNo.01.pdf
AD1-1 requires the signed acknowledgment page with the proposal. AD1-5 replaces
the email-only wording with email plus six hardcopies of technical and fee
proposals in separate sealed envelopes. Recipients and delivery details must
still be confirmed in the complete RFP.

`app/core/submission_checklist.py` pins the reviewed addendum and its parent RFP
hashes. Exact source, record ID, contract and RFP URL scope this pilot to the
reviewed procurement. No title or agency-name fuzzy matching is permitted.

Instructions are withheld on different/missing hashes, failed checks, changed
addendum inventory, or checks older than 48 hours (also invalid/future dates).
Closed/inactive records do not receive an actionable checklist. An unchanged
hash establishes only byte identity with reviewed evidence, not bid completeness.

Before changing a pinned hash, read the replacement document and all new addenda,
update instructions and review date, and run the focused suite. Never advance
hashes automatically to make the warning disappear. Keep historical change flags
independent of this human-reviewed baseline. Production checks run with the
existing source refresh; page rendering makes no network requests.

Validation: mobile 390x844 and desktop 1280x800 inspected locally. Tests in
`test_bid_readiness.SubmissionChecklistTests` cover identity, unchanged records,
mutations, failed/stale/future checks, addenda and rendered instruction suppression.
