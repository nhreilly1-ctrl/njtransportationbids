# Return-use acceptance criteria

Companion to `docs/RETURN_USE_PLAN.md`. Each criterion is written to become a
test. "Snapshot" means the notice data the visitor actually saw, identified by the
`generated_at` of the `health_summary.json` produced in the same crawl run.

Repository facts these rest on (main at `3b7c7a4`): change timestamps are the crawl
run's time, not agency publication or deployment time; each crawl commits notices
and health together; `git push` without rebase means only one overlapping crawl run
lands, so a landed run's change stamps are later than the previous landed
snapshot's `generated_at`. Deployment to Render follows the commit by some minutes.

## Stage 1 — My Work

### A. Baseline and time

| ID | Given | Then |
|---|---|---|
| A1 | Snapshot S generated 09:18 and live; a crawl stamps a change at 16:44 that deploys at 17:05; the visitor loads the page at 16:50, still seeing S, and returns tomorrow | The 16:44 change is shown. **The baseline is S's `generated_at`, never the request time.** A request-time baseline (16:50) would hide the change permanently |
| A2 | The visitor presses "Mark reviewed" | The baseline becomes the `generated_at` of the snapshot on screen, not the click time |
| A3 | The browser clock is a day fast or slow | Same sections, same badges. The browser clock is never read for comparisons |
| A4 | The stored baseline is missing, naive, or unparseable | Treated as a first visit: no "new" badges, no change lists. Never treated as the epoch, which would mark everything new |
| A5 | A change is detected at `2026-10-15T03:30:00+00:00` | Grouped under Wednesday, Oct 14 (Eastern) |
| A6 | Any change timestamp is displayed | Worded "Detected Oct 14", never "Changed" or "Published". Footnote: our daily check found it; the agency may have changed it earlier |

### B. Saved items

| ID | Given | Then |
|---|---|---|
| B1 | IDs saved under `njtbids.shortlist.v1` before My Work shipped | They appear in My Work unchanged. Same key, no migration step that can lose them |
| B2 | Stored shortlist data fails validation (`read()` throws) | The page still renders, explains the problem, and offers Reset. Reset is a first visit |
| B3 | A saved ID is absent from the snapshot entirely | Shown as "No longer published on this site" until the visitor removes it; never silently dropped |
| B4 | A saved record is expired / `source_inactive` (e.g. `notice-09a31913dc62`) | Shown in a Closed group with its last known deadline; absent from "closes next" |
| B5 | A saved record is later noise-flagged or deleted | "Removed from this site's coverage", not silent disappearance |
| B6 | Saving `notice-75297aa782eb` (US-1 Raritan forecast) | Does not save, badge or attach changes to `notice-09a31913dc62` (the US-1 Raritan construction contract), and vice versa |

### C. Changes on saved items

| ID | Given | Then |
|---|---|---|
| C1 | `changes_since(record, baseline)` returns `complete=False` | Show what was recorded plus "Changes before {date} weren't recorded"; never imply there were none |
| C2 | A forecast's window moves | One change: "Expected window changed". **Currently fails**: labelled "Deadline changed" and "Forecast changed". Pinned by `test_forecast_window_move_is_not_reported_as_a_deadline_change` (expected failure) |
| C3 | Any field change | History stores labels, not previous values. Show the current value ("now Spring 2027"); never show or imply the previous one |
| C4 | A forecast is removed from its source listing | "No longer on {agency}'s anticipated list. The agency doesn't say whether it was advertised, delayed or dropped." Never "cancelled" or "awarded" |
| C5 | A bid is removed from its source listing | "No longer on the agency's current listing", with no implied outcome |
| C6 | A document fingerprint changes | "Document updated: check the official copy". Not "review required", which reads as an instruction we are not entitled to give |

### D. New in my view

| ID | Given | Then |
|---|---|---|
| D1 | A record has `first_seen_at` after the baseline | Eligible for "Newly listed". Records without `first_seen_at` go to "Discovery date not recorded" and are never badged new |
| D2 | First visit | Zero "new" badges |
| D3 | A record without a contract number is retitled by its agency (new ID, fresh `first_seen_at`) | Known limitation: it will read as new. Either label the group "Newly listed or renamed" or state the limitation once; decide before launch. Title similarity must never be used to merge them |
| D4 | A location or work-focus preference is set | Matching records first, then "Location not stated" and "Other / unclear" groups. Unknown is shown, never filtered away |

### E. Upcoming work watch

| ID | Given | Then |
|---|---|---|
| E1 | A forecast window has passed | "Expected window has passed; advertisement not confirmed" (existing behaviour) |
| E2 | A forecast and an open bid look alike (same route, structure, county) | No link, no "now advertised", no merged card without an official shared identifier |
| E3 | Any forecast | Never listed under "Which saved bids close next" |

### F. Saved bids closing next

| ID | Given | Then |
|---|---|---|
| F1 | Saved open bids | Ordered by normalized Eastern deadline; date-only shows "time not published" |
| F2 | `deadline_conflict` | Conflict wording, not a single date |
| F3 | Any record | No meeting, question or addenda promise. Live coverage of those fields is zero |

### G. Freshness and failures

| ID | Given | Then |
|---|---|---|
| G1 | A saved item's source is stale or failed in the health summary | That state is shown beside the item |
| G2 | A refresh fails | No changes, no "removed" state, no new badges result from it |

## Stage 2 — Training event schema

One record per dated session; multi-day courses use `sessions`.

| Field | Required | Notes |
|---|---|---|
| `id` | yes | Stable: provider + provider event URL or ID + first session start |
| `provider_name`, `provider_url` | yes | Issuer of the event, not a reseller |
| `title` | yes | Verbatim |
| `audience_text` | no | Verbatim |
| `topic` | yes | Bounded: `work_zone`, `flagger`, `inspection`, `materials_testing`, `construction_safety`, `dbe_support`, `other` |
| `sessions[]` | yes, ≥ 1 | `{start, end?, precision: datetime\|date, timezone}`; `timezone` required when `precision` is `datetime` |
| `registration` | yes | `{url, status: open\|closed\|unknown, deadline?}`. Deadline only when published; never derived from the start date |
| `event_status` | yes | `scheduled`, `cancelled` or `rescheduled` |
| `delivery` | yes | `in_person`, `online`, `hybrid` or `unknown`; `location_text` optional |
| `fee_text`, `prerequisites_text`, `credit_text` | no | Verbatim; absent renders as "Not stated by provider" |
| `source_url`, `last_verified_at`, `last_verification_state` | yes | State is `ok` or `failed` |

Invariants, each a test:

1. Listed only if a session starts on or after today (Eastern), `event_status` is
   not `cancelled`, and `registration.status` is not `closed`.
2. A date without a year is rejected, never assumed current. This covers the 2025
   flyer case in the plan.
3. A failed verification keeps the last good data labelled "Last verified {date}";
   past a set age it is hidden. The age is a curator decision; record it.
4. `credit_text` is never synthesized, and topic never implies a contract requirement.
5. Events never count toward bid, notice or source totals.

## Stage 2 — Credential entry (extends `resource_catalog.py`)

Existing catalog fields (`title`, `agency`, `url`, `audience`, `what`, `contains`,
`use_when`), plus:

- `kind`: `company_certification`, `agency_prequalification` or `individual_credential`
- `issuing_body`
- `renewal_source_url`: the official page describing renewal. Never a computed date

No personal data and no eligibility decisions. Renewal intervals appear only as
quoted text with that source URL.

## Copy review: current change labels

| Current | Proposed | Why |
|---|---|---|
| Deadline changed (on a forecast) | Expected window changed | Forecasts have no deadline (C2) |
| Removed from agency listing | Forecast: "No longer on {agency}'s anticipated list". Bid: "No longer on the agency's current listing" | "Removed" reads as cancellation (C4, C5) |
| Document changed; review required | Document updated: check the official copy | Not our instruction to give (C6) |
| Changed {date} | Detected {date} | Our check time, not the agency's (A6) |
| Notice text changed | Keep | Accurate and neutral |
| Returned to agency listing | Keep | Accurate |
