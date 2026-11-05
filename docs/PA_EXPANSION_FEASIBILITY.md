# Pennsylvania transportation index: feasibility assessment

Checked November 4, 2026 (America/New_York). Repository baseline: `9ae1208`.
Research only: no PA source was added to production, no generated NJ data was
changed, and no account, subscription, domain or hosting service was purchased.

## Recommendation

Proceed with a bounded technical pilot, conditional on reliable access to
PennDOT's current advertisements. Pennsylvania has useful official public
content and enough source fragmentation to make a unified index plausible.
It is not yet established that PA will be as inexpensive to maintain as NJ,
or that it is the easiest second state. A broad statewide launch is premature.

The lowest-risk initial source set is PennDOT's public construction forecast,
Turnpike construction advertisements, and a small, explicitly named selection
of county public-works listings. PennDOT current construction and consultant
advertisements are the central unresolved coverage dependency. SEPTA and PRT
should not be promised until their collection paths are proven.

## Method and evidence limits

Exa returned 25 search results across five targeted searches: PennDOT, Turnpike,
transit agencies, local procurement, and structured forecast alternatives.
Repeated URLs were consolidated; results were leads, not proof of live access.
Validation used ordinary anonymous HTTP, read-only public search/detail forms,
browser observation and official PDF extraction. No ECMS guest session was
entered. First pages of the forecast and Turnpike notice were rendered and
visually inspected; the entire forecast was not parsed into project records.
These are point-in-time observations, not a longitudinal uptime study.

## Source assessment

| Source | Verified on November 4 | Pilot treatment / remaining work |
| --- | --- | --- |
| [PennDOT current construction / consultant opportunities](https://www.pa.gov/services/penndot/find-contract-information-bid-opportunities) | Public agency page loads and links ECMS. The production ECMS entry loads with Guest access. Official [guest instructions](https://www.sbe.penndot.pa.gov/SBEWeb/sbe/roadConstruct.do) describe advertised bid packages, consultant planned projects and public searches. Acceptance of its restricted-use notice was blocked by automatic approval review. | Required gate for a credible PennDOT open-bid board. Current record counts, pagination, revisions, document downloads, stable links and complete-listing semantics remain unverified. Public instructions do not by themselves establish authorized automated reuse. |
| [PennDOT planned 12-month letting schedule](https://docs.penndot.pa.gov/Public/Bureaus/BOCM/Let%20Schedules/letschdl.pdf) | Direct HTTP 200; 215,073-byte, 38-page PDF dated November 4, covering November 4, 2026 to November 4, 2027. Fields include ECMS/MPMS IDs, district, county, route, scope, cost range and anticipated letting date. It says it excludes currently advertised ECMS projects and will be revised monthly. | Strong Upcoming source. Never label its anticipated letting dates as verified closing deadlines. Repeated ECMS numbers represent component rows, not necessarily separate opportunities. Test grouped projects, wrapped descriptions and multiple MPMS IDs. A directly public spreadsheet/feed alternative was not verified. |
| [PA Turnpike EBS construction schedule](https://ebs.paturnpike.com/generalinformation/bids/bid_schedule.aspx?type=Advertised) | Direct HTTP 200 and browser listing agree on three advertised contracts. Public session/postback navigation opens details, scope summary, addenda summary and a Notice to Bidders PDF. Downloading the EBS bid file requires registration. | Best proven open-construction source. Needs a dedicated ASP.NET session/postback adapter, complete pagination and document-content validation. Detail URLs are session-dependent; publish the reliable schedule link plus exact contract identity until a durable deep link is proven. |
| [SEPTA published bid list](https://wwww.septa.org/procurement/bids/) and [public bid search](https://epsadmin.septa.org/vendorbidsearch) | Search/fetch service exposes relevant catenary, bridge, accessibility and construction-management listings. Direct HTTP to the published list returns 403. Public ePS search returns 200, but View All produced no visible results in this check. | Unresolved, not launch-ready. Do not interpret search-indexed listings as a current complete feed or the empty search as proof of zero opportunities. Resolve an agency-supported public path and pagination first. |
| [PRT procurement](https://rideprt.org/business-resources/procurement/) | Old Bids and RFPs URL redirects to Business Resources. The current procurement page links [Open Purchasing Events](https://rideprt.org/business-resources/procurement/open-purchasing-events/), which returns 200 but no event rows in retrieved HTML. | Defer. An empty page body is not an authoritative empty listing. Current completeness, documents and amendments remain unverified. |
| [Allegheny County Public Works](https://www.alleghenycounty.us/Projects-and-Initiatives/Doing-Business-with-Allegheny-County-Bids-and-Solicitations/Public-Works-Bids-and-Proposals) | Direct HTTP 200. Public Open Solicitations section has a Neville Township traffic-improvement SOI due December 2, a Becks Run Road slope-stabilization bid due November 18 at 11:30 AM prevailing local time, and a continuously open appraisal assignment. Each has an advertisement PDF link. | Good limited county pilot source. Two clearly transportation-related advertisements were identified; the appraisal assignment needs scope review. PDF links were observed, not individually downloaded. Submission uses Bonfire or ECMS; discovery and submission access must be described separately. |

The [Turnpike Business Hub](https://www.paturnpike.com/business-hub) directs
highway engineering/architectural RFPs to PennDOT ECMS. Construction EBS alone
therefore does not cover Turnpike engineering opportunities. Likewise,
Allegheny is one county sample, not a statewide county-coverage audit.

## Representative document check

Turnpike contract **EN-00335-03-04**, sinkhole repairs between mileposts 187.00
and 312.03, appears on the public Advertised schedule. Anonymous read-only
postback navigation retrieved its summary and two-page Notice to Bidders.
The notice and summary agree on **November 17, 2026 at 11:00 AM local time**.
The addendum summary explicitly reports no addenda for this sample.

The existing `app/core/bid_documents.py` functions independently recognized
the exact contract identity and extracted `2026-11-17` with raw submission
time `November 17, 2026 at 11:00 AM`. This supports reuse of the document
decision logic; it does not prove all PA notice formats or amended deadlines.
The collector currently recognizes direct `.pdf` URLs and specific NJ detail
pages, so it cannot collect this form-delivered `.aspx` PDF unchanged.

Document SHA-256:

- Forecast: `10d806096a6cdd56cb58effebc5ad17748dcd3c3ec5e45a9a2148f903d80e77f`.
- Turnpike notice: `c44df9e956e4cd5af3983bf9a660d3ce2cf20c2ac1c5f22366205b9e95143751`.

## Application reuse and necessary changes

Evidence from reachable code at the stated baseline:

| Reuse | Adapt before a public PA deployment |
| --- | --- |
| Deadline normalization, forecast states, document ordering/identity checks, change history, complete-listing lifecycle, CSV/calendar and board components | Add PA retrieval adapters and source policies; document ordering remains by published version/date, never download time. Registration-gated or unsupported documents remain explicit review states. |
| Existing source registry and orchestration pattern | Replace the global NJ registry/data-path assumptions with explicit site configuration. Keep datasets, source-health totals and crawl logs separate; a missing PA dataset must never fall back to NJ records. |
| Conservative geography approach | `app/core/geography.py` and `crawlers/source_health.py` embed NJ counties. `app/core/corridors.py` has NJ route/place assumptions. Add PA county/route rules and state-scoped provenance without treating a route or agency jurisdiction as county evidence. |
| Flask templates, public search, shortlist and SEO infrastructure | `app/main.py` and templates embed NJ labels/agency defaults. `base.html` only enables GA for NJ production hosts; `SITE_URL` is configurable but branding is not fully configurable. Calendar UID domain also embeds NJ. Configure per-site branding, canonical domain, analytics, source coverage and assets. |

Recommended implementation: one maintained codebase and independently
configured site deployments. Separate data and scheduled jobs can preserve
NJ reliability while PA adapters mature. Do not copy the repository into an
independently diverging PA fork. No code migration was implemented in this pass.

## Pilot scope and launch gates

Proposed scope is an official-source index of road/bridge/heavy civil work and
relevant engineering services. Publish undated advertised work, keep forecasts
separate, and hand users to the issuing agency. Exclude general commodities,
unrelated purchases and unverified scope; do not claim complete PA coverage.

Before launch:

1. Resolve authorized PennDOT current-advertisement access, or explicitly
   choose a narrower product without PennDOT open-bid coverage. Do not silently
   substitute its forecast for current advertisements.
2. Prove complete listing traversal, stable source handoff and latest-document
   extraction for every included agency. Test ordinary ads, numbered addenda,
   moved deadlines, undated ads, disappearance, empty pages, HTTP failures,
   pagination and format changes. Failed/partial checks must retain listings.
3. Add site configuration, geography isolation and NJ regression coverage.
   Confirm a PA host cannot serve NJ fallback data or send events to NJ GA.
4. Run at least 14 days of shadow collection, manually compare a small sample
   of records to controlling advertisements, and log every intervention. A
   quiet two weeks does not replace amendment/withdrawal fixtures.
5. Track Google search clicks, official-source outbound clicks and return use
   separately by state. NJ's screenshot has zero key events; actual bid-document
   handoffs need validated measurement before treating traffic as useful leads.

Suggested decision budget, not a measured operating cost: average at most one
hour of human intervention per week after setup. Record parser repair time as
well as routine checks. Stop adding sources if they require recurring manual
login, document copying or unverifiable deadline fixes. There is no defensible
build-cost or ongoing-maintenance estimate yet; ECMS access and a shadow run
are prerequisites. PA search demand, competition, revenue, domain availability,
paid conversion and longitudinal source reliability were not measured here.

## Access limitation

ECMS presented a notice restricting use to authorized government business.
Automatic approval review rejected accepting it for this private feasibility
assessment. No workaround, alternate guest endpoint or credentials were used.
This is a limit on the verification performed, not a legal conclusion that
PennDOT forbids public procurement indexing. A further guest-access check
requires evidence of authorization and user approval, or an agency-supported
public feed that does not require crossing that notice.
