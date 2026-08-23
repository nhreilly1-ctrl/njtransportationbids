# Zero-record county audit — 2026-08-23

Closes the open item from the 2026-08-21/22 audit session: *"Seven counties with
zero records (Atlantic, Gloucester, Hunterdon, Middlesex, Salem, Sussex, Hudson)
— never verified against health_summary.json."*

Evidence used: `data/notices/health_summary.json`, `data/notices/crawl_log.json`,
`data/notices/notices.json`, `crawlers/notice_sources.py`,
`crawlers/notice_crawlers.py`, `crawlers/source_health.py`, and the unit tests in
`test_notice_pipeline.py`. **Live pages were not fetched** — this environment's
network egress policy blocks the county sites — so nothing below is a claim about
what any source page currently displays. Live confirmation of the two flagged
parsers belongs to a session with real HTTP access.

## Headline findings

1. **`health_summary.json` could not have answered the question.** Its
   `coverage.missing_counties` measures *configured sources* (it has read `[]`
   since all 21 counties got sources), not records. Fixed in this change:
   coverage now also reports `counties_never_produced` (no crawl of any of the
   county's sources has ever recorded a positive count),
   `county_active_records`, and `counties_without_active_records`.

2. **Salem is resolved.** It now carries one active record (as-needed traffic
   signal maintenance) with `NOTICE_TEXT` geography evidence
   (`title:"County of Salem"`). Its parser is proven.

3. **Six counties have never produced a single record in any crawl:** Atlantic,
   Gloucester, Hudson, Hunterdon, Middlesex, Sussex (Warren is the seventh
   never-producer, but is human-verified expected-empty). For these, `status:
   "ok"` proves only that the crawl executed and that `allow_empty` policy
   accepts zero — it is silent on whether the parser can see the page's
   listings. There is no baseline proving parser sight for any of them.

4. Ten counties currently have zero *active* records; the additional three
   (Burlington, Essex, Passaic) are sources that **have** produced —
   their prior records were correctly noise-flagged chrome or expired and
   retired — so they are working sources with nothing currently in scope.

## Per-source assessment of the six never-producers

| Source | Parser | Structural guard | Unit test | Assessment |
|---|---|---|---|---|
| county-atlantic | `bidexpress_agency` | Raises if "Upcoming Solicitations" table missing | Yes | Recent crawls clean → table found, rows filtered. Zero plausibly genuine. Two fetch failures (8/17, 8/19) hint at intermittent bot detection; parser also reads *only* the "Upcoming Solicitations" section of the agency page. |
| county-gloucester | `gloucester_county` | **None** — any 200 page with no matching `<tr>` yields silent 0 | No | **Cannot distinguish "no bids" from parser blindness.** This is exactly the failure mode Somerset had. Highest priority for live verification. |
| county-hudson | `hudson_county` | Raises if table headers change | Yes | Clean crawls prove the table exists with expected schema. Jersey City publishes on BidNet (registration-walled). Zero plausibly genuine. |
| county-hunterdon | `generic_html_list` | None; also requires bid keywords **and** transport keywords in the anchor text itself | No | Only **one** successful crawl ever (weekly cadence; the other attempt failed to fetch). CivicPlus bid-schedule pages often link documents with bare titles that would fail the anchor-text gate. High blindness risk; evidence extremely thin. |
| county-middlesex | `opengov` | Raises if OpenGov server state missing/changed | Yes | Clean crawls → portal state parsed, zero open transportation projects at crawl time. Good confidence in the parser; a zero for a county this size is still worth an occasional manual look. |
| county-sussex | `bonfire` | Raises if portal JSON changes | No (but same parser produces Bergen's record live) | Parser proven on Bergen. Only one successful crawl ever. Zero plausibly genuine for a small county. |

**Recommended follow-up (needs live HTTP access):** fetch the Gloucester and
Hunterdon pages, confirm whether they currently list any bids, and either add a
structural sentinel (Gloucester has no equivalent of Hudson's schema check, so a
layout change can never be detected) or record them as verified-empty the way
Warren was. No parser changes were made here — without seeing the live pages,
adding a guard risks breaking a working source.

## Related audits closed with this change

**Dedupe (162 records / 18 shared `official_url`s, em-dash contract variants).**
Now 170 records across 22 shared URLs; the clusters are records that only have a
listing-page or shared-PDF URL (NJDOT prof-serv current + anticipated, NJ
Transit PDF, NJTA listing), not duplicated notices. Among **active** records
there are zero duplicate `(source_id, normalized contract_number)` pairs and
zero duplicate normalized titles. The 22 `TP — NNN` / `TP-NNN` spelling variants
are all pairs of one active record plus one correctly retired `source_inactive`
ghost, created when NJDOT changed its own punctuation; dedupe's exact-match
contract rule missed them, the lifecycle retirement covered for it. Cost is
record-lineage discontinuity and inflated raw counts (295 total vs 166 active),
not public duplication. A normalized-contract dedupe key would prevent future
splits but must respect the AGENTS.md identity-rule bar (fixtures for
amendments/reissues) — not attempted here.

**Geography evidence model spot-check (current data).** All audited defect
classes remain fixed: the three concatenated multi-notice records are retired;
DRJTBC records are `BISTATE` with empty county lists; chrome-titled records are
`UNRESOLVED`/noise; county-source `SINGLE_COUNTY` claims all rest on
`geography_provenance: NOTICE_TEXT` with explicit matched tokens (the
`AGENCY_JURISDICTION` value on those records is the provenance of the preserved
raw `county` field, not of the normalized claim). Active-record geography:
41/166 with evidenced counties, scopes `SINGLE_COUNTY` 34, `MULTI_COUNTY` 7,
`BISTATE` 13, `REGIONAL` 29, `STATEWIDE` 21, `UNRESOLVED` 62; zero records
flagged for geography review.
