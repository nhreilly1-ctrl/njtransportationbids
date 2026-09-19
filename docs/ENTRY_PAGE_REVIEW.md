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

Official documents examined:

- https://dot.nj.gov/transportation/contribute/business/procurement/ConstrServ/documents/NOTICETOCONTRACTORS_DP26107.pdf
- https://dot.nj.gov/transportation/contribute/business/procurement/ConstrServ/documents/NOTICETOCONTRACTORS_DP26121.pdf

Measure official-document exits, research-tool clicks, related-work clicks and
shortlist saves. More page views alone are not the definition of success.
