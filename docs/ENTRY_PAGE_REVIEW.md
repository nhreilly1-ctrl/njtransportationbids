# Entry-page review, September 18, 2026

Scope comes from the user's September 9-15 Search Console Pages screenshot,
not a current analytics API export:

| Entry | Clicks | Improvements |
| --- | ---: | --- |
| Route 1 construction, notice-09a31913dc62 | 9 | Shorter heading with full source text retained, section shortcuts, explicit related-work status, NJDOT research pilot |
| Homepage | 5 | Direct route / project / contract search across active notices |
| Construction list | 4 | Separate later-closing open bids from forecasts; no urgency styling for conflicted deadlines; clarify full-dataset CSV export |
| Route 94, notice-52f61899ea44 | 4 | Scannable published facts, shorter heading, research and related-work shortcuts |
| Route 1 professional forecast, notice-75297aa782eb | 3 | Direct research and related-work paths without presenting the forecast as an open construction bid |

## Verification

- PR 21 research pilot merged as b090eea; production research sections confirmed
  on all three project pages using Chrome at 390x844 and 1440x1000.
- These same five pages checked locally at both sizes. No horizontal overflow
  or JavaScript page errors. Homepage first project title at y=726 on 390x844;
  official source actions visible on the first screen of all three project pages.
- Source titles, URLs, canonical URLs, SEO identifiers and stored records remain
  unchanged. Only the visible NJDOT construction heading drops trailing funding
  and administrative identifiers; full wording remains in expandable source text.
- Research links are reference directories, not matched traffic counts, cameras,
  soil conditions or verified site findings. Camera playback was not verified:
  the local network blocks the 511NJ viewer.
- Analytics QA blocks Google collection and tests dispatch locally. This does not
  establish receipt or conversions in the production GA4 property.

## Live-source finding requiring follow-up

The official DP26107 PDF retrieved on September 18 still says August 25, 2026,
while the current Route 1 listing says September 24. Do not promote that PDF's
10 AM time to the current deadline. DP26121's PDF does agree with its September
24 listing and explicitly publishes 10 AM. A future document-deadline pilot
must check contract identity, agreement with the current listing, freshness and
conflicts before exposing an exact time or calendar event.

September 19 safeguard: the first-page collector now retains the explicitly
labelled Project Bid Date with PDF identity, hash and retrieval time. Fresh,
identity-matched disagreement with the listing is disclosed on the project page
and excluded from reliable closing-soon groups and calendar exports. The listing
date is retained, not replaced by the older PDF date. Conflicting PDF-derived
estimate/completion/qualification facts are withheld. Exact bid-time enrichment
remains deferred; no agency-wide default time has been assumed.
An old or failed PDF recheck does not silently clear a known discrepancy:
previous date evidence is retained for the same record/contract/document only,
labelled as needing recheck, and never used to republish stale project facts.
A successful matching document check clears that warning.

The NJDOT-only refresh after rebasing onto the September 19 automated snapshot
retained all 359 records. Semantic changes were limited to 12 NJDOT construction
records: check metadata and PDF evidence, plus Route 1's conflict/urgency fields.
Other agency records were unchanged. The generated JSON has a larger textual
diff because the runner reorders serialized fields. Source health was 45 healthy,
2 warnings, 0 errors after this local refresh.

PR 22's five entry pages were also verified in production at 390 and 1440 pixels:
search submission, notice redirect, project section jumps, saved shortlist after
reload, full agency text disclosure, related navigation and closing groups all
passed. Google Analytics collection was blocked during these tests.

Official documents examined:

- https://dot.nj.gov/transportation/contribute/business/procurement/ConstrServ/documents/NOTICETOCONTRACTORS_DP26107.pdf
- https://dot.nj.gov/transportation/contribute/business/procurement/ConstrServ/documents/NOTICETOCONTRACTORS_DP26121.pdf

Measure official-document exits, research-tool clicks, related-work clicks and
shortlist saves. More page views alone are not the definition of success.
