# Accuracy and engagement checkpoint - 2026-09-08

Priority order: accuracy/coverage, discovery/return visits, useful-action
measurement, targeted agency intelligence. Do not expand dossiers to fill space.

## Verified coverage findings

Warren's RFP table now has RFP Number, Title, Starting, Closing, Status. The
parser supports this exact alternate schema while retaining Somerset's schema.
Starting is never the deadline. Live read-only check returned zero scoped work;
the current RFP row was auditing services, not transportation. Unknown schemas
still fail explicitly. Legal-notice extraction remains separate.

Cumberland remains an open repair task. Direct inspection of the official index
confirmed FeedID links for 26-40 Federal Road Program and 26-39 Survey Services.
Details embed official PDFs; a dedicated parser and deadline fixtures are needed.
Do not silence its zero-record error or claim the opportunities have been recovered.

Gemini completed a bounded two-county investigation in 116.82 seconds. Its
Cumberland leads were confirmed against official HTML. Its Warren root-cause
explanation missed the separate RFP component and was not used as the fix.
Research output is in the sibling agency-requirements-pilot directory,
coverage-response-2026-09-08.json, not runtime data.

## Measurement contract

- shortlist_saved / shortlist_removed: emitted only after storage succeeds;
  public notice_id only. Analytics failure must not undo or misreport a save.
- agency_guide_open: project-to-guide link; agency slug, public notice ID and surface.
- agency_guidance_click: official guidance click from agency guide; agency and surface.
- Existing filter_applied and official-source/map/resource events remain unchanged.

No saved-list contents, search text, proposal contents or user identity are added.
These events are not proof of successful bid submission. A removed shortlist item
is not necessarily a negative signal. GA4 blocking/consent means counts are partial.
Unit tests stub gtag and send no real analytics requests.

After deployment use GA4 Events to compare shortlist saves, official-document
clicks and guide use. Register agency/surface event-scoped custom dimensions if
breakdowns are wanted. This code change does not configure the private GA4 account
or prove receipt of events in its reports. Avoid drawing conclusions from tiny counts.
