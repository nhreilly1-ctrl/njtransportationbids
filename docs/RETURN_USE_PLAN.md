# Return-use delivery plan

Finalized direction: October 13, 2026. This is an implementation plan, not a
claim that these changes are deployed. Equipment exchange and a general message
board are deferred. No accounts, email alerts, chatbot or payments in this suite.

## Product promise and audience

"See what changed, plan upcoming work, and stay ready to pursue it."

First pilot: consultant pursuit leads and civil-contractor estimators. Training
also serves safety/training coordinators. Subs and suppliers retain access to
all work; do not promise plan-holder or award coverage we do not have.
Audience size is unmeasured. Recruit ten businesses for validation with the
owner's approval rather than designing around an invented market total.

Keep the current digital-feed visual language and existing bid pages. No giant
hero, forced onboarding, or new dashboard replacing the useful default view.

## Delivery order

### 0. Close unused account surfaces and establish trustworthy change tracking

First implementation change: retire legacy /network routes including registration,
login and all write paths, with explicit 410/404 behavior and tests. Check current
templates for url_for references before unregistering the blueprint. Retain any
existing data securely; do not delete it or claim no accounts exist. Redirect
useful resource URLs only where a real maintained equivalent exists. This is
containment, not a claim that a complete security audit has been performed.

Evidence: on October 13 an unauthenticated read-only GET of the public
/network/register returned 200 and company/email/password inputs. Main registers
network_bp; network_models._hash uses unsalted SHA-256. No registration was
submitted, no user records inspected. Actual hosting disk settings and historical
data loss are not verified by render.yaml alone.

Review Claude's bounded history patch and reproduce its coverage audit before
merging. Test ordinary refreshes, multiple changes, migration, retention cap,
removal/reappearance, timestamps and unsuccessful source checks. Describe entries
as changes detected by our index; timestamps are not agency publication times.
History labels alone are not before/after values: do not display invented deltas.

Identity is a separate guarded change: compare normalized identifiers only within
source and compatible procurement context, with amendment/reissue/reused-number
fixtures. Keep raw identifiers and durable aliases for old saved IDs if continuity
is proven. Ambiguous records remain separate. No title-only forecast linking.
Do not make all launches wait for solving identifier-free forecasts; show their
continuity limitations rather than claiming reliable per-project tracking.

Gate: focused Python tests, scanning/identity fixtures, compileall, JS tests where
affected, CI and live verification. Review generated history after a real run.

### 1. My Work, with an Upcoming Work Watch section

Extend the existing shortlist, not a second saved-items system. Add a compact
My Work entry reachable from every project page. Existing visitors keep saved IDs.
Optional work-focus, agency and evidenced-location preferences are editable inline.
No mandatory two-question wizard; default all work remains available.

The return view answers four questions in this order:
- What changed on saved projects? Verified change labels, time and source link.
- What is newly discovered in my view? Only supported first_seen_at timestamps.
- What upcoming work should I watch? Forecast windows, detected window changes,
  passed windows and no-longer-listed states, distinct from open bids.
- Which saved bids close next? Normalized deadlines, not missing addenda promises.

Show unknown-location and unknown-discovery groups with explanations. First visit
sets a server-derived baseline without labelling everything new. Mark reviewed is
explicit. Use a server response timestamp consistent with the displayed snapshot,
not the newest check from one source as proof all sources were refreshed. Expose
per-source stale/failure states. Browser clock skew cannot alter the baseline.
State same-browser-only storage; reset is a first visit. Truncated history is
labelled incomplete. Closed/unavailable saved items remain understandable.

Gate: desktop/mobile visual QA, keyboard access, old-shortlist migration, empty and
first-visit tests, capped/missing history, clock boundaries, false-new identity
tests and honest behavior under failed refresh. No confirmed forecast-to-bid links
without additional official identity evidence. No wording promising missed-event
protection or comprehensive project updates.

### 2. Training & Credentials pilot, delivered alongside stage 1 where independent

Add a dated Training & Events view under Resources, cross-linked from My Work;
keep events structurally separate from bid records and bid/source counts. Reuse
date/time utilities, not notice lifecycle semantics or procurement classifications.
Events need start/end, cancellation and registration status; a course start is
not its enrollment deadline. Multi-day sessions need explicit treatment.

Each item: provider, audience, explicit dated session, time/timezone or precision
label, online/location, published fee, prerequisites, credits as stated, official
registration URL and last successful verification. Missing optional data stays
unknown; no inferred certification or contract eligibility. Provider handles
enrollment and documents. Closed registration and cancelled events are not shown
as available; stale retrieval is labelled, not silently passed off as current.

Verified source feasibility on October 13:
- Rutgers CAIT https://cait.rutgers.edu/event/tccroct/ publishes an explicit
  2026-10-15 session, audience, fee, prerequisites, credit wording and registration
  link. No explicit registration deadline confirmed. Structured API coverage not
  yet tested; detail-page extraction is feasible, not proven production-ready.
- https://www.bridgetosuccess.com/njdotssp---training-sessions-2026 calls its
  February-April 2026 workshops upcoming. They are past at review time. Do not
  populate an October pilot from that label. Keep the program as a resource.

Start with a small genuinely useful verified list, even if initially one provider.
Do not pad to fifteen events or delay a good pilot solely to hit two providers.
Clearly label pilot coverage and expand only after source checks. No manually
maintained promise unless a curator and review cadence are assigned.

Credentials extends resource_catalog: company certification, agency
prequalification, individual credentials. Describe issuing body, intended user,
purpose, and official application/renewal source. No personal credential vault or
automatic eligibility decisions. Record this staying-ready scope in TIME_AND_TOOLS
with the implementation; all existing accuracy/no-account rules remain.

Gate: yearless and past-event guards, stale/cancelled/rescheduled/multi-day tests,
missing fee/credit/deadline handling, provider links and mobile readability checked.

### 3. Calendar subscriptions

After stages 1 and 2: subscribe to a stable public filter view, not a browser-local
shortlist that calendar servers cannot access. Keep bid and training feeds separate.
Only exact dated items become calendar events; forecasts stay windows on the site.
Stable UIDs, updates, cancellations, date-only all-day handling, timezones and
rescheduling must be tested. Explain client refresh delays; never advertise it as
an urgent addendum alert. One-time downloads and subscriptions are distinct actions.

## Validation and collaboration

Codex: containment, history review, audit reproduction, identity decision, source
verification, implementation and live release checks. Claude: adversarial tests,
bounded event/credential schema and copy review. One implementation owner per change.
No further speculative feature brainstorming until these gates yield a release.

Before measurement, verify actual receipt of existing analytics events and isolate
internal tests. Track useful return visits with saved-item/source actions and
provider registration outbound clicks; outbound clicks are not completed enrollment.
Inspect page paths, not summed title rows or active-minus-new user arithmetic.
Run a six-week pilot with a three-week check. Ten weekly returning businesses is
a validation goal, not forecast. Collect task-based feedback and steps saved.
Low clicks with low exposure are inconclusive, not an automatic kill criterion.
Pause expansion for incorrect dates, stale content or maintenance beyond capacity.

Deferred: equipment/message board, email/accounts, price indices, bid-tab analytics,
plan-holder aggregation, unsupported project-stage linking and generic chatbots.
These are not rejected permanently; they do not block this focused UX release.
