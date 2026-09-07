# DRJTBC schedule pilot

Scope: `state-drjtbc-profserv` only. Read labeled fields inside each official
`div.entry.row`, never the first date on the page or a different project's dates.
Keep pre-proposal meetings and inquiry deadlines separate from solicitation closing.
Raw text, source fragment URL, and evidence travel with each milestone.

Verification on September 7, 2026:
- C-753A: closes September 17; meeting August 18 at 10am; inquiries August 25.
- CM-552A: closes September 10; meeting August 18 at 2pm; inquiries August 27.
- CM-816A and CM-809A have elapsed June closing dates and remain historical.
- Four unique source IDs, eight milestones. The investment advisory RFP is excluded.

Source: https://www.drjtbc.org/professional-services/current/

Times have no published zone in this listing, so Eastern is explicitly assumed.
Inquiry dates have no time. Passed milestones are labeled; no attendance requirement,
meeting location, or cancellation is inferred. Official amendments remain authoritative.
This pilot does not extract linked PDF amendments. Users must confirm those documents.

The old paragraph-prefix identity collides across three CM contracts. New records use
agency entry IDs; old URLs remain stored and become inactive after a successful source
refresh. Do not redirect a collided legacy URL to one arbitrarily selected project.
Generated notice data is not edited by this patch. A source refresh is required after
deployment to populate the fields. Inspect resulting record counts before expansion.

Checks completed: live Edge mobile shortlist save/reload/remove at 390x844;
representative map query evidence retained for Route 1/Raritan, Bailey's Mill/I-287,
Spring Valley/CR-601, Marlboro's three roads, and six-route North drainage work.
Map checks validate search inputs, not Google's resulting location or project limits.

Run the focused workflow suite including `test_milestones`, plus both Node test files.
