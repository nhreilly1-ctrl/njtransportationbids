# NJDOT research tools pilot

## Scope and placement

`app/core/project_research.py` routes a maximum of four small reference groups
on NJDOT construction, professional-services and design-build detail pages.
Other agencies and data pipelines are unchanged. Public notices, noise and
deleted records do not get a pack. Closed projects retain explicitly general
references, not claims about historical or current site conditions.

Official documents, map actions, deadline calendar and shortlist remain first.
Project facts and agency schedule retain their priority. Agency preparation and
research follow the project summary, ahead of related work. Duplicate record
fields are collapsed for this pilot; nonpilot detail layouts remain unchanged.

Routing uses title evidence and existing professional-service type. It does not
change notice type, county, map, deadline, eligibility, or contract facts.
Mixed bridge/paving work prioritizes site context. Viewers are not preselected
to a project. All title route references are retained; no route/county pairing.

## References checked 2026-09-17

- Roadway diagrams/imagery: https://dot.nj.gov/transportation/refdata/sldiag/
- Public camera directory: https://511nj.org/camera
  Public purpose confirmed at https://www.nj.gov/transportation/commuter/511/web.shtm
  The directory is JavaScript-rendered. No individual camera field of view was
  verified. Do not label this link "nearby camera", embed feeds, or promise video
  availability. Start with the directory; future camera matching needs reviewed
  road, direction, milepost, location and provider-supported links/reuse terms.
- Traffic/AADT viewer directory: https://dot.nj.gov/transportation/refdata/gis/arcgis.shtm
- Historical prices: https://dot.nj.gov/transportation/business/aashtoware/estimation.shtm
  Visible reports include 2022 and 2023 quarters. Do not call these current prices.
- Price indices: https://dot.nj.gov/transportation/business/aashtoware/PriceIndex.shtm
  Current dated table retrieved, but no values copied into notice records.
- Borings: https://dot.nj.gov/transportation/refdata/geologic/index.shtml
  Current page describes the updated GDMS viewer and its reference-only limits.
- Environment: https://dep.nj.gov/gis/nj-geoweb/
- Consultant workflow: https://dot.nj.gov/transportation/business/procurement/ProfServ/
- Submission references: https://dot.nj.gov/transportation/business/procurement/ProfServ/techprop.shtm
- Project background uses only the reviewed structure evidence already in
  `app/core/project_maps.py`; it is not inferred from arbitrary URLs or keywords.

Some NJDOT www.nj.gov URLs are HTML meta-refresh redirects, not content. Check
the dot.nj.gov destination and page text; HTTP 200 alone is insufficient.

## Meeting/weather boundary

No NJDOT records in the inspected snapshot carry structured future meeting
locations and attendance requirements. The pilot does not generate a meeting
calendar from a bid deadline, a forecast from a county centroid or a project pin,
or attendance rules from agency boilerplate. Existing published agency schedules
and deadline calendar behavior are preserved. Meeting-specific location,
attendance, calendar and short-range forecast tools remain gated on collecting
and verifying those source fields; they are not implemented by this link pilot.

## Measurement and operation

No network requests, third-party scripts, embeds, API keys, or paid services are
added to page rendering. Links work without JavaScript. `project_research_click`
uses the existing analytics handler with resource ID, group, notice ID, agency,
type and surface. Compare use of cameras, traffic counts, background and pricing
against official-source clicks and saves before expanding integrations. Do not
use extra pageviews as the success criterion.

Run `python -m unittest test_project_research` and `node test_analytics.cjs`.
The new suite also runs in the public-site PR gate. Link checks are manual;
network access is not required by regression tests.

## Validation 2026-09-18

- 274 focused Python regressions passed, plus analytics/shortlist Node tests,
  compileall and diff whitespace checks.
- Headless Chrome at 390x844 and 1440x1000: Route 1 construction, Route 1
  professional-services forecast and Route 94. Research links fit the viewport,
  record details expand, saves survive reload, and research click events carry
  notice/resource IDs. No page JavaScript errors observed. Screenshots reviewed.
- A pre-existing closing-mode fixture froze the deadline clock but not
  `eastern_today`; the test now freezes both. Production lifecycle is unchanged.
- Direct browser access to 511NJ returned a network-firewall 403 during the
  final check. Its application HTML was retrievable and NJDOT documents the
  public camera directory, but camera playback/list rendering was not verified.
  No individual-camera availability or field-of-view claim is published.
- Meeting/forecast additions remain deferred as described above.
