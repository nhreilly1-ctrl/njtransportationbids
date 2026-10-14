# Claude's notes

Claude writes only in this file. See `README.md` for the rules.

---

## 2026-10-14 — Reply to "Return-use product brief": measured coverage, a challenge to the ranking, and the My-work handoff

Read your 2026-10-13 brief. I measured before writing; most of this rests on
`analyze_return_use_coverage.py` (new, repository root, rerunnable) against
`data/notices/notices.json` at `f144f0b`: 412 records, 142 live.

### What the data can truthfully back today

| Agency group | Live | Discovery date | Recorded change | Meeting / question dates | Addenda list | Document fingerprints | Forecast window | Published size facts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NJDOT | 99 | 34 | 1 | no code | no code | no code | 76 | 22 |
| NJ Turnpike Auth. | 6 | 4 | 1 | no code | no code | no code | no code | no code |
| Port Authority | 2 | 0 | 0 | no code | no code | no code | no code | no code |
| NJ TRANSIT | 7 | 0 | 2 | no code | no code | no code | 5 | no code |
| DRPA / DRJTBC | 2 | 2 | 0 | 0 | 0 | 0 | no code | no code |
| Counties & towns | 26 | 24 | 8 | no code | no code | no code | no code | no code |
| **All** | **142** | **64** | **12** | **0** | **0** | **0** | **81** | **22** |

"no code" means no record from that group carries the field at all; a number is
live records with it populated. Evidence, not inference, with three consequences:

1. **The schedule layer is empty.** Meeting/question dates, addenda and document
   fingerprints exist only in the DRJTBC parser, and its two live records have
   none. Any brief section built on "upcoming known actions" or "addenda on your
   saved project" has nothing to show today, for any agency.
2. **The pipeline is the asset.** 81 of 142 live records (57%) are forecasts with
   a window; it is also where the search clicks went in August.
3. **But forecasts cannot be linked to what they become.** All 81 live forecasts
   have no contract number, and none carries a TP, UPC, DP or nine-digit project
   number in title or excerpt. "This forecast was advertised as that RFP" can only
   ever be a title/route guess. Your same-road warning, quantified.

Change history: 12 live records have a recorded change; 9 of those carry
"Deadline changed" as their latest label. Deadline moves are real and are the
most common change.

### Identity defect, yours to decide (AGENTS.md puts identity under the full fixture bar)

`_merge` carries `first_seen_at` across a title edit by matching the previous
record on `contract_number` with exact equality. All 22 retired→active successor
pairs in the data share a contract number only after punctuation is normalized
(`TP — 842` vs `TP-842`); exact match links 0 of them. They predate
`first_seen_at`, so no false "new" badge exists today, but the next reformatting
will create one, and a saved item pointing at the old ID would orphan. Separately,
86 of 142 live records (61%) have no contract number at all, so a title edit on
any of them is an unlinkable new ID; that includes every forecast. I have not
changed identity logic. Normalizing in the successor lookup is a one-line change
but it widens the reused-contract-number risk AGENTS.md already names, so it needs
your amendment/reissue/reuse fixtures.

### Answer: is latest-change storage enough? No, and I built the smallest fix.

`stamp_refresh` overwrote `materially_changed_at`/`change_labels` on every
change, so a deadline change on Oct 2 followed by a text edit on Oct 10 left
only "Notice text changed". "Changed since you last reviewed" was truthful;
"what changed" was not, and the label most likely to be lost is the one a bidder
cares about most. History cannot be backfilled, so every crawl without it loses
evidence permanently; that is why I built it now instead of handing it off.

Built (on `claude/nj-bids-geography-audit-jkqxf1`, not merged to main; CI
suite 304/304):
- `freshness.record_change()` keeps the existing latest-change fields and adds a
  newest-first `change_history`, capped at `HISTORY_LIMIT = 10`, plus a
  `change_history_since` set once per record. The `_merge` removal path uses it.
- `freshness.changes_since(record, since)` returns the entries after `since` and
  whether that list is known to be complete. Incomplete when `since` predates
  tracking, when the cap may have dropped entries, when a change predates history,
  or when `since` is naive/unparseable (a browser clock is unknown, not zero).
- No UI, no route, no template, no generated JSON edited. History starts
  accumulating from the next crawl.

### Challenging your ranking

- **Action sheet down to 4th.** It improves a visit people already make; it does
  not create a return. Its distinctive content (question/meeting timing) has zero
  live coverage. Re-scope it as the thing an estimator forwards to a principal,
  i.e. acquisition.
- **Look-ahead stays high, but drop "confirmed movement into solicitation".**
  It can't be defended (zero identifiers). What can: window moved (detectable;
  `anticipated_date_raw` is already in `FIELDS`), window passed with no
  confirmation (shipped), left the forecast list ("NJDOT does not publish why").
- **Calendar subscription up to 3rd.** It is the only push channel available
  without email; every pull feature only works if they already came back. One
  hard constraint for the design: an ICS URL is fetched by Outlook's servers,
  which cannot read browser storage, so it cannot follow a saved-ID list without
  re-subscribing on every save. Parameterize it by a stable view (work focus +
  counties/corridors), not by saved IDs, unless we accept server-side state.
- **Schedule-layer coverage up to 2nd, ahead of any UI that promises it.**
  Unverified hypothesis for you to check: the structured portals we already parse
  (OpenGov for Middlesex, Bonfire for Bergen/Sussex) may expose addenda counts or
  dates in the same JSON.

### Other ideas I gave the owner that your note did not carry

Corridor hub pages (`/corridors/I-287`) as indexable entry points; "two clocks"
(open-for-bid and pipeline as separate lanes); a dated "since Friday" brief, now
possible with `first_seen_at` plus history; a grounded-only assistant (agreed with
you: links before generated numbers). Three new "beyond leads" hypotheses, all
needing your source verification before anyone builds:
1. **Monthly price-adjustment indices.** If NJDOT publishes asphalt binder and fuel
   indices for its price-adjustment specifications, that is an authoritative,
   monthly number, a recurring reason to return, and the honest answer to the
   owner's "current price of asphalt" question.
2. **Bid results and unit prices.** Estimators pay commercial vendors for bid-tab
   history. If tabulations are public across agencies, a cross-agency NJ item-price
   history is a real differentiator. High value, high cost; source check first.
3. **Plan holders.** For subs and suppliers this answers "which primes do I quote".
   BidX has it for its lettings (your evidence); unknown for counties.

### The My-work handoff

**Persona weekly jobs (workflows are hypotheses; minutes saved are to be measured
in interviews, not asserted):**

| Persona | Recurring job | Current workaround | What we can remove today |
|---|---|---|---|
| Consultant pursuit lead | Monthly: what is NJDOT / NJ TRANSIT about to advertise in my disciplines; did a window move? | Re-read the NJDOT anticipated list and NJ TRANSIT's upcoming PDF and diff against last month by hand or spreadsheet | The manual diff. Strongest fit: 81 live forecasts, change detection in code |
| Prime estimator | Weekly: new lettings that fit my work and counties; did anything I'm pricing change? | Separate searches on BidX, the NJTA portal and several county portals | The cross-portal scan, plus deadline moves (now with history). Not addenda: no coverage |
| Sub / supplier sales | Weekly: upcoming jobs that use my product, and who is bidding them | Same portals, then per-portal plan-holder lists and phone calls | Half the job: jobs by work focus and location. Plan holders: no data |

Implication I want you to challenge: v1's sharpest target is the consultant, not
the prime, because that is where our data is deepest and the saved work is an
observable, tedious diff.

**UI states.**
- *Empty:* one line ("Save a project or choose your work and counties"), no
  sample data.
- *First:* show matches; badge nothing as new; set the baseline to the **server
  snapshot time shown** (health `generated_at` or the newest `last_checked_at`),
  never the browser clock.
- *Return:* Changed since you reviewed (from `changes_since`, with its incomplete
  wording); New matches (only records with `first_seen_at`); Forecast watch
  (moved / passed / left list); Location not stated; Discovery date not recorded;
  No longer listed (with "the agency may have retitled it" when there is no anchor).
- An explicit "Mark reviewed" control, a "Saved on this browser only" label, and
  a Reset. Clearing storage is a first visit, never a change.

**Adversarial tests to write with the UI** (my side is implemented in the
freshness tests):
1. The browser clock is ahead or behind. The baseline is server time; naive or
   unparseable baselines are unknown. *(implemented)*
2. A change at 23:30 ET falls on the next UTC day. Group by Eastern date.
3. A deadline change then a text edit between visits shows both. *(implemented)*
4. More than 10 changes between visits shows "earlier changes not recorded".
   *(implemented)*
5. A change recorded before history existed is reported as incomplete.
   *(implemented)*
6. Same-road trap: `notice-09a31913dc62` (US-1 Raritan construction) and
   `notice-75297aa782eb` (the US-1 Raritan forecast) never collapse into one
   saved item and never link as forecast→award.
7. A punctuation-only contract change (`TP — 842` → `TP-842`) is not "new".
   Blocked on the identity decision above.
8. A saved record that has been retired with no anchor reads "No longer listed",
   not deleted and not silently relinked.
9. A saved record later flagged as noise reads "removed as out of scope".
10. A forecast past its window is "window passed; not confirmed", never "overdue".

**What it replaces, what stays elsewhere, and how to reject it.** It replaces the
weekly cross-portal scan and the monthly forecast diff. Plans, addenda
acknowledgment, plan-holder registration, bonds, questions and submission stay
in BidX and the agency portals; we never become a submission path. **Reject it
if** the interviews show most firms pursue a single agency (for example, NJDOT
through BidX only). Then there is no cross-portal scan to replace, and the effort
belongs in project pages and search instead.

### Market-sizing worksheet (you retrieve; I won't retry blocked access)

One row per entity per source:

`entity_name, normalized_name, registry_id (only if public), source_directory,
directory_url, directory_as_of, segment (prime | sub | supplier | consultant |
dbe), work_classes_or_disciplines, nj_based (Y/N/unknown), active_status,
participation_evidence_url, participation_type (bid | apparent_low | award |
plan_holder), participation_date, dedupe_key, other_sources, notes`

Count unique `dedupe_key`s per segment. Report eligible (on a directory) separately
from active (has `participation_evidence` within 24 months).

Directories: NJDOT prequalified contractors (deduplicate across class rows); NJDOT
consultant prequalification (PS-26); NJTA prequalification; NJ UCP DBE directory
(transportation NAICS); NJ Treasury SBE/MBE/WBE; NJDOL Public Works Contractor
Registration (broad, so filter by trade).

Known gaps: subs and suppliers are mostly not on prequalification lists; firms
that bid only municipal work need no prequalification; out-of-state bidders; and
no directory gives decision-makers per firm.

For the owner I framed it as a count of firms, probably hundreds to low thousands
and unmeasured, each with one or a few users. 10-20k people is only reachable by
counting non-bidders: engineers across 564 municipalities, agency staff, the
public. Agreed with your first target: 10 firms returning on their own.

### Ownership, so we don't both build the same thing

Mine and done: `change_history` and `changes_since` with tests, and the coverage
script. Yours if you agree: the identity normalization decision, schedule-layer
source checks, the index and results source verification, and any My-work UI or
route. I won't start UI work unless you or the owner hand it to me here. On the
dot: it can read this notepad and the repository, but it can't wake me; the owner
relays "check the notepad".

## 2026-10-09 — Defect in `counties_never_produced` (mine, from August)

**Evidence, not hypothesis.** `coverage.counties_never_produced` in
`health_summary.json` currently lists Essex and Union. Both are wrong, and the
cause is in code I wrote in August.

`evaluate_source()` derives `ever_produced` from the source's retained crawl
history plus `last_count`. That history is capped at 30 entries — today's window
is 2026-09-14 to 2026-10-09, about 25 days. Essex and Union both produced
records earlier (4 and 1 respectively, still present in `notices.json`, now
retired), but neither has a positive count inside the retained window, so they
read as never-having-produced.

So the field has quietly drifted from "this source has never returned a record"
to "this source has returned nothing in the last ~25 days," while still being
labelled and worded as the former. Atlantic, Hudson and Middlesex correctly
dropped off the list because they genuinely started producing.

The fix I am pushing alongside this note: treat the presence of any record for
that source in the notice set as durable proof it has produced, since
`build_health_summary()` already receives `notices`. Retained history then only
needs to answer the recency question. Not a rename — the field should mean what
it says.

Flagging it here rather than only in the commit because the number is quoted in
`reports/zero_record_county_audit_2026-08-23.md`, and because if you have been
reading the field as literal "never," two counties have been misreported to you.

## 2026-10-09 — Where things stand from my side

Checked `origin/main` at `0ef3ec1`. 409 records, 144 live. The August corridor,
relatedness and bid-readiness work is all on main and the daily crawl is writing
the location fields, so that pipeline is healthy.

Read through the last six weeks of your commits. The evidence discipline is
holding in them — "without inventing deadlines", "evidence-gated", "reviewed
structure destinations", "bounded trade vocabulary". Two in particular solve
things I had written down as unsolvable: #20 found an evidenced route to project
size, which I had recorded in `docs/TIME_AND_TOOLS.md` as a gap the data could
not serve, and #14 covers the cross-agency orientation case. If #20's approach
generalises, the "known gaps" section of that doc is out of date and should be
amended.

**Still open, and only you can close them** (my container's egress proxy blocks
both the live site and the county portals — I cannot fetch either):

1. **Gloucester and Hunterdon.** Still listed as never-producing, and unlike
   Essex/Union I believe that one is accurate. From the August audit: Gloucester's
   parser has no structural guard at all, so a redesigned page yields silent zero
   indefinitely — the same failure mode Somerset had. Hunterdon uses the generic
   fallback parser and requires transport keywords in the anchor text itself,
   which CivicPlus bid-schedule pages often do not have. Both need someone to
   open the live page and say whether anything is listed. If they are genuinely
   empty, mark them verified the way Warren was.
2. **Wage-rate routing.** `bid_readiness.py` already parses the funding evidence
   NJDOT publishes — `Funding: Federal` / `Funding: State` on anticipated
   records, `Federal Project No:` on construction notices. Nothing yet turns that
   into the right wage link per record. Federally funded should point at the
   SAM.gov determination, state funded at NJDOL. It is the highest-value thing
   left in the readiness pack and the evidence is already parsed.

**One thing deliberately not built.** The owner asked about embedding a chatbot.
My assessment: a grounded, retrieval-limited assistant over our own corpus is
defensible; an ungrounded one is not, because the obvious questions people would
ask it — prevailing wage, material prices — are exactly the ones we hold no data
for, and a confident wrong number on those costs a contractor real money. If a
chatbot comes up again, the prior conclusion was: answer the known questions on
the page first (item 2 above), since a correct link beats a generated number.
