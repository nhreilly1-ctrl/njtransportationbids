# Gloucester and Hunterdon: live verification, October 9, 2026

## Evidence and method

Read both official pages through the web reader, then fetched the live HTML with
the application's `_get` helper (configured browser-style headers) and inspected
the actual BeautifulSoup elements. Both helper requests returned HTTP 200.
Plain requests without those headers returned 404; that is not proof the pages
are absent. Ran both repaired parsers directly, without the runner, so this
verification did not write production notices or crawl history.

- Gloucester: https://www.gloucestercountynj.gov/bids.aspx
- Hunterdon: https://www.co.hunterdon.nj.us/2913/2026-Bid-Schedule

## Gloucester

**Evidence:** the direct fetch contains seven open CivicPlus bid cards, not table
rows. Their identifiers are PD-26-031, PD-26-038, PD-26-041, RFP-26-043,
RFP-26-044, RFP-26-045, and RFP-26-046. The web reader exposed only the first
four. The direct response is the basis for the count here.

**Scope assessment:** the advertised subjects concern an amphitheater, event
rentals, a warming center, tax counsel, animal control, property-title services,
and septic inspections. None of those listing titles establishes transportation
or covered heavy-civil project work under the current scope policy. No full bid
packages were reviewed; septic inspections in particular should not be relabeled
as transportation engineering merely because an engineering firm is requested.

**Confirmed defect and repair:** the old parser iterated `tr` elements and could
not see these cards. The replacement reads `.bidItems .listItemsRow.bid`, checks
the title/status/deadline structure before scope filtering, preserves the
published status/time, and raises on missing or changed structure. A missing
layout is not accepted as an empty listing. Synthetic positive and negative
fixtures reproduce the observed card structure.

**Verified outcome:** zero currently matching records on this check, not an
empty procurement page. This does not establish future completeness or that the
source has historically produced a record.

## Hunterdon

**Evidence:** the schedule says last updated October 7. It contains 15 numbered
rows. Transportation rows include historical road resurfacing, bridge painting,
road materials, and traffic striping. Awarded/cancelled rows must not become live
opportunities. The remaining future-dated row is 2026-15, landscape maintenance
and mowing, due October 29 at 11 AM. Its title does not state roadway scope.

**Confirmed defect and repair:** commodity titles are unlinked table text. The
generic anchor parser could not extract them. A dedicated parser now validates
all seven column headers and row widths, reads titles/dates/times from cells,
excludes awards, cancellations, and elapsed bid dates, and applies existing
transportation scope rules. Tests include unlinked titles, date-only notices,
unrelated mowing, awarded/cancelled work, and changed layouts.

**Verified outcome:** zero current matching transportation records. Historical
transportation work exists, so this is not a county with no transportation bids.
The dated verification is recorded here, like the earlier Warren assessment;
no fabricated record or permanent healthy/ever-produced override was added.

## Remaining uncertainty

We did not read gated bid packages or resolve the scope of general mowing/septic
services beyond the published listings. Broader inclusion would be a scope
decision requiring project evidence, not a parser workaround. The annual
Hunterdon schedule URL will require a rollover check when the county publishes
its next year's schedule.
