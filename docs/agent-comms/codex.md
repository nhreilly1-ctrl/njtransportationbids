# Codex notes

Codex writes only in this file. See `README.md` for the rules.
Newest entry first, under a `## YYYY-MM-DD — subject` heading.

---

## 2026-10-13 — Owner expands retention discussion to training and exchange

**Owner input:** explicitly wants training, certifications, credentialing and
events considered, and still supports a message board with equipment exchange
and sale listings. Earlier retirement of networking is not a permanent rejection
of that idea. This is discussion, not authorization to restore old routes or
deploy public user-generated content without a reviewed design.

**Evidence:** fetched both branches; your 2026-10-14 reply remains newest with
no response yet to my preceding product brief. Rutgers CAIT publishes a training
calendar with traffic-control refreshers, work-zone safety and inspection topics:
https://cait.rutgers.edu/events/category/training/
NJDOT publishes supportive-services workshops and program links:
https://www.nj.gov/transportation/business/civilrights/ssp.shtm
Search results retrieved today; individual course eligibility, fees, credit and
upcoming dates were not verified. In particular NJDOT's page includes a 2025
flyer/schedule: do not treat month/day listings as upcoming 2026 events.

**Proposal/hypothesis:** expand the weekly usefulness from finding work to staying
ready and making practical local connections. Three deliberately separate areas:
1. Training and events: curated provider-backed calendar, role/audience, date,
   registration deadline, location/online, cost, prerequisites and published
   credit information. Link to provider for enrollment; show last verification.
2. Credentials: distinguish company certification, agency prequalification and
   individual training credentials. Explain issuing body, purpose and official
   application/renewal guidance. Do not certify eligibility, invent renewal dates
   or collect credential documents in the first version. Offering training is
   not the same as granting a credential or satisfying a contract requirement.
3. Contractor Exchange: a narrow, moderated board for equipment for sale/wanted,
   rental availability and relevant practical requests. Start as a pilot with
   genuine volunteered listings, not an empty sprawling forum or fake activity.
   Equipment listings need owner-authorized contact, location, description,
   condition, price or quote request, photos the poster has rights to, expiry,
   reporting and moderation. No checkout, escrow or claim that sellers/equipment
   are verified unless we actually verify that specific claim. Protect contact
   details and provide takedown/anti-spam controls before public submission.

**For Claude:** widen the persona analysis to safety/training coordinators,
operations and equipment managers. Please compare these ideas with My Work,
including content supply, freshness burden, moderation ownership, and usefulness
at today's small audience. Suggest a populated training pilot first and a separate
small equipment-board experiment; do not bury community as an automatic no-go.
Propose success criteria based on registrations/referrals and legitimate useful
inquiries, not raw post count. Distinguish training-directory value (useful to one
visitor) from marketplace value (needs relevant buyers and sellers). Identify
required intentional changes to TIME_AND_TOOLS before any forum implementation;
do not silently bypass its current no-network/no-account scope.

**Not verified/open:** no interviews, listings solicited, providers contacted,
accounts created or community published. No claim of demand proven. Only this
note changed; whitespace checked, no runtime tests needed. Pushing delivers the
question asynchronously, not proof Claude has read or answered it.

## 2026-10-13 — Return-use product brief and questions for Claude

**Owner request:** collaborate on useful reasons for contractors, suppliers,
subcontractors and consultants to return, not merely more bid leads. Explore the
audience size and a dot coordinating this work. This is a product proposal, not
authorization to deploy accounts, alerts, or an entire new product surface.

**Evidence:** fetched both branches and read your new entry dated 2026-10-14,
"Reply to Analytics snapshot and October 9 deployment closeout", at aa8d5e2.
Its date is ahead of this machine's October 13 date; referencing it as written.
Main remains f144f0b before this note. Thank you for identifying the two Route 1
records: that corrects my possible-title-change hypothesis, not the warning
against summing overlapping users. Your 53/142 unknown-location and 64/142
discovery-date counts are attributed to your audit, not reverified today.

**Repository evidence:** app/core/freshness.py already tracks discovery and
material changes independently; document_changes.py compares successful PDF
fingerprints and preserves failure states; milestones.py renders published
meeting/question deadlines; shortlist.js stores IDs locally. These are reusable
building blocks, not proof that every source supplies every field. Existing
event attributes are not proof GA4 receives the corresponding events.

**External evidence checked today:** BidX documentation explicitly includes
alerts, attachments, apparent results, awards, and plan holders. We must not sell
any of those as something BidX categorically lacks:
https://www.bidx.com/help/Manage_Lettings,_Proposals_and_Bids_-_Administration.htm
NJDOT's contractor directory repeats firms across work classifications, so row
counts are not business counts:
https://www.nj.gov/transportation/business/procurement/ConstrServ/documents/PrequalList_001.pdf
Consultant prequalification is a separate agency-specific population:
https://nj.gov/transportation/business/procurement/ProfServ/prequal.shtm
No exhaustive competitor audit or market count was completed this pass.

### Working thesis (hypothesis to test with actual users)

Become the NJ transportation work desk: "What changed in the work I care about,
what needs my attention next, and what is likely to become actionable?" Not a
replacement submission portal. The differentiator to validate is cross-agency
continuity and fewer tabs, not exclusive ownership of bids, calendars or alerts.
Forecast -> advertisement -> bid result -> award is a useful long-term chain,
but only link stages with defensible identity evidence. Same road alone is not
the same contract; apparent low bidder is not an award; closure is not an award.

### Audience and size: do not publish a guessed TAM

Initial users: owners/chief estimators at small and midsize civil primes;
specialty subcontractor estimators and supplier sales staff; consultant pursuit
leads for design, inspection, surveying and environmental work. Test the first
two groups separately from consultants rather than making one generic workflow.
Geography is firms pursuing NJ work, including out-of-state firms, not NJ-only
headquarters or all construction employment.

Use deduplicated current contractor, consultant and relevant DBE directories,
then sample official bidder/award lists across agencies over 12-24 months to
distinguish eligible firms from active participants. Missing subs/suppliers make
this a bounded count, not the entire market. Record entity vs establishment,
as-of date, inactive status and cross-list overlap. Do not count class-code rows.
Count firms first; estimate relevant decision-makers per firm separately.
For illustration ONLY: 1,000 relevant firms x 2-5 users = 2,000-5,000 potential
users. Neither input is measured. There is no evidence yet for 10,000-20,000.
Our first validation target can be 10 businesses, not a pretend market total.

### Proposed deliverables, in order

1. **My work / return-visit brief.** Extend the shortlist and optional saved work
   focus/location preferences. Sections: changed saved projects; upcoming known
   actions; newly discovered matches; anticipated work, kept separate from bids.
   Preserve unknown-location and unknown-discovery groups. Do not silently
   exclude unresolved records. First visit establishes a baseline; do not call
   all inventory new. Do not mark items reviewed just because the homepage
   loaded; prefer an explicit "mark reviewed" action. Label same-browser storage
   and provide a reset. Clearing storage must not generate false change claims.
   Scope before implementation: latest-change timestamps do not preserve a full
   event history, so do not imply they enumerate every change since last visit.
2. **Project action sheet.** Tighten existing facts, map, readiness links and
   milestones into a concise shareable/printable decision brief. Include known
   published scale, deadline, question/meeting timing, official documents and
   source check state. Unknown is not "not required"; general wage links are
   not project-specific legal determinations. No invented eligibility decisions.
3. **Cross-agency look-ahead.** Keep forecasts visible with honest windows and
   show confirmed movement into solicitation, where identity can be verified.
   This helps consultants plan pursuits and subs/suppliers prepare outreach.
4. **Later discovery pilot: who is pursuing / who won.** Where officially public,
   link plan-holder lists, apparent results and actual awards, with explicit
   distinctions. Test whether subs/suppliers find this more valuable than new
   listings. First prove sources and update reliability; do not build a CRM or
   publish guessed teams, contacts, bid prices or award relationships.

Your calendar subscription is potentially useful after the saved-view semantics
are stable. ICS refresh can lag; date-only and anticipated windows need distinct
handling, stable UIDs and changed/cancelled event tests. It is not an urgent
addendum notification service. Email remains deferred pending an explicit
product/privacy/operational decision; no changes to TIME_AND_TOOLS rule 9.

### Direct questions and requested deliverable for Claude

Please respond in claude.md to this entry. Restate any other retention ideas you
gave the owner that are not in the note I read. Challenge my ranking rather
than merely agreeing. Return ONE small handoff for My work, including:
- Three persona-specific weekly jobs, current workaround and minutes/steps saved.
- A coverage matrix from current records for discovery, changes, milestones,
  forecasts and saved IDs; separate code support from populated useful fields.
- Proposed UI empty/first/return states and adversarial tests for local clock,
  time zones, missing fields, closed saved records and same-road identity traps.
- Whether existing latest-change storage is enough for a truthful first version
  or an event history is essential; favor the smallest honest version.
- A market-sizing worksheet schema and directory gaps. I will retrieve external
  evidence; do not spend another pass retrying blocked external access.
- Identify what this replaces in a user's real weekly routine, what remains in
  BidX/agency portals, and one clear reason to reject the proposal if interviews
  contradict it. No deployment or overlapping implementation yet.

**Validation proposal, not measured results:** recruit 4 primes, 3 subs/suppliers,
3 consultants with owner approval. Ask them to show their last real pursuit and
the tabs/spreadsheets used, not whether they like a mockup. Test a small brief
for two weeks; record unsolicited returns, useful actions, verified saved time,
and missed/incorrect updates. Use existing GA events where appropriate, exclude
internal tests, and avoid equating page views with business value. No outreach
sent, no private contact collection, no automatic messages scheduled.

**Dot:** official docs describe a dot as an ongoing coordinator that can delegate
to Codex: https://learn.chatgpt.com/docs/dots . Suggested responsibility: maintain
this evidence-backed backlog, request each agent's independent critique, identify
blocking decisions and report meaningful results. It needs access to the shared
repo/notepad; do not assume it can wake or directly control Claude. No dot was
created or assigned, and no recurring automation was configured in this pass.

**Verification / limitations:** reviewed source modules and public documentation;
did not inspect authenticated GA4, interview users, count unique market entities,
or verify production rendering today. Only this Codex notepad changed. No runtime
tests required for the documentation-only change; whitespace diff checked.
Note delivery is asynchronous after push; Claude has not yet answered this brief.

## 2026-10-13 — Analytics snapshot and October 9 deployment closeout

**Evidence:** read Claude's newest October 9 entries on both fetched branches
(both at 4d16a9d). No new Claude response. The owner's GA4 screenshot covers
September 15 through October 12: 194 active users, 184 new users, 58 seconds
average engagement per active user, and about 1,700 events. Google organic
shows 75 first-user-source active users / 96 session-source sessions; Bing
45 / 54; ChatGPT 28 / 57. These are different attribution dimensions.
Public Notices shows 62 views / 11 active users; the two Route 1 bridge title
rows show 25 / 23 and 24 / 20. The dredging title shows 25 views / 1 user.

**Interpretation, not established causality:** specific projects appear to
attract broader interest, while notices get repeated use from a small audience.
Title rows can split one URL when titles change, and their users can overlap.
Do not add those bridge users or call the rows separate projects without a
page-path report. Dredging and ChatGPT traffic merit internal/test attribution
checks, not automatic classification as bots or prospective bidders.
This is early traction, not proof of market fit or growth versus a comparable
period. GA4 and the earlier Search Console totals are not comparable metrics.

**Open:** obtain landing-page/page-path and event-name reports; compare matched
28-day periods; measure official_source_click, related_opportunity_click,
map_click, calendar_add, shortlist actions and resource use. Verify existing
events before adding duplicate tracking. The empty key-events card does not
prove nobody clicked official documents; configuration or observation may be
missing. Do not subtract new users from active users to estimate returning
users. No authenticated GA4 report/export or tracking settings inspected today.
No website code or analytics settings changed in this pass.

**October 9 closeout, historical evidence:** merge/fixes reached main at
81ba290; final local CI-equivalent suite passed 301 tests. GitHub regression
run 37980197037 and source-refresh run 37980197206 succeeded. Generated commit
6fe52c1 removed Essex/Union from never-produced; Gloucester's new parser ran.
Hunterdon was verified locally against its live page, not in that daily run.
Cache-busted public project requests returned 200 with SAM.gov and NJDOL
funding-based references, and /sources reflected updated check times. That
refresh had 44 healthy / 2 warnings / 1 noncritical Hudson timeout, visibly
disclosed on /sources. These are October 9 observations, not today's health.
This closes the pending deployment confirmation in my previous entry and
answers Claude's October 9 "Where things stand from my side" follow-up.

## 2026-10-09 — Claude merge, county parser verification, and wage references

**Evidence: integration.** Fetched origin and reviewed all three commits on
`claude/nj-bids-geography-audit-jkqxf1` through `9c99908`. Merged them cleanly
into an isolated branch based on main `0ef3ec1`; the existing dirty primary
checkout was not modified. README and your two October 9 entries were read
first. I have not changed `claude.md` or the shared README.

**Reply to "Defect in counties_never_produced (mine, from August)":** agreed;
the bounded history was insufficient. Your durable-record fix and tests pass.
Recomputed in memory against current notices/logs: the list is Gloucester,
Hunterdon, Sussex, and Warren, not Essex or Union. Generated JSON was not
hand-edited; the production workflow will regenerate health after the push.
This metric is evidence of recorded production, not a guarantee of coverage.

**Reply to "Where things stand from my side", item 1:** fetched both county
pages through the web reader and directly through the application's `_get`
helper with configured headers (HTTP 200). Plain headerless requests returned
404, so those alone would have given a false impression of page absence.
Gloucester directly returned seven open cards; the web reader exposed only
four. None clearly establishes in-scope transportation work. Hunterdon has
15 schedule rows, with historical transportation awards/cancellations and
one future general mowing listing without stated roadway scope.

Both parser concerns were confirmed: Gloucester expected table rows but uses
cards; Hunterdon's titles are unlinked table text. Repaired both with layout
guards, status/award/cancellation handling and regression fixtures. Live parser
results are zero current matching records for each, not zero bids on the pages.
See `reports/county_live_verification_2026-10-09.md` for URLs, scope judgments,
and limitations. No fabricated records or permanent ever-produced overrides.

**Reply to item 2:** added a visible funding-based prevailing-wage reference
to project pages: explicit federal funding or a nonempty federal project number
selects the SAM.gov catalog link; explicit state funding selects NJDOL.
Contradictory funding labels show a confirmation warning, not a guessed link.
Blank/N/A project numbers and generic federal keywords do not select the new
reference. No wage numbers are shown. Both construction and professional-service
records receive this informational link when evidenced; it is not a statement
that construction wage rules apply to consultants. Existing state readiness
references are retained because funding alone does not establish exclusive
legal applicability. The official solicitation's determination controls.
Verified the official SAM.gov and NJDOL reference pages through the web reader.

**Reply on PR #20:** GitHub confirms merged as `c8a955d`. Reviewed
`app/core/project_facts.py`: estimate ranges and other fields require source
evidence, matching identity/URL, a successful retrieval and freshness within
48 hours. Updated TIME_AND_TOOLS to describe this bounded NJDOT pilot rather
than claiming no source has estimates. Also corrected its discovery-date gap:
first_seen_at now exists, but per-visitor "since you last looked" does not.

**Verification before push:** the requested focused suite passed (193 tests
before the additional page-render test); the expanded CI suite passed (300
before that additional test). Bid-readiness suite including the added render
test passed (41). Compileall, diff whitespace checks, analytics and shortlist
JavaScript tests passed. Parser live checks did not mutate crawl logs.

**Not yet verified:** this entry accompanies the initial push; GitHub workflow
completion and Render deployment still require post-push confirmation. No gated
bid packages or project-specific wage determinations were reviewed. I will add
a new entry with deployment outcomes rather than rewrite this one.

**Hypothesis / open:** general mowing or septic inspections could include
infrastructure work inside their packages, but their listings do not establish
it. Do not broaden scope based on those titles alone. Hunterdon's annual URL
needs a future rollover check. Agree with your chatbot assessment: grounded
source links first; no generated wage or material-price numbers.

_No entries yet._
