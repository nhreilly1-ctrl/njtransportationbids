# Official forecast reconciliation - September 5, 2026

## Evidence

- NJDOT index: https://www.nj.gov/transportation/business/procurement/ProfServ/AnticipatedSolic.shtm
- Read all four linked XLSX workbooks using the parser, with current-solicitation comparison enabled.
- NJ TRANSIT calendar: https://www.njtransit.com/procurement/calendar/
- NJ TRANSIT forecast: https://content.njtransit.com/sites/default/files/pdfs/Upcoming_Procurement_Opps_August-2026.pdf
- NJ TRANSIT calendar was independently read in Chrome; the PDF publication date is August 19, 2026.

## Results

Corrected NJDOT parsing returns 76 candidate forecasts, including 13 with elapsed windows: 12 Spring 2026 and one Summer 2026 (May/June). These are still visible in the current agency workbooks; elapsed timing alone must not retire them. Current-solicitation title matching remains heuristic, not proof that no renamed advertisement exists.

The Operations workbook contains hidden historical rows. Reading values alone admitted them. The corrected parser skips hidden rows and sheets. This reduces the initial experimental 118 candidates to 76; the 118 count was not published.

NJDOT explicitly defines Summer 2026 as July-September. Its ordinary summer forecasts remain within their window. Winter year labels are ambiguous across the index and workbook conventions and remain unresolved rather than receiving an invented end date.

NJ TRANSIT yields five scoped forecasts: three August windows have elapsed (Roosevelt Avenue bridge, ALP-45 engineering, RiverLINE engineering), while Howell tanks and Task Order D2/D4 retain their September/October windows. The year comes from the PDF publication date, never the refresh timestamp. The original period text is preserved.

The older RiverLINE RFP 0000239 is marked cancelled in the calendar. That must not cancel the later August forecast by association. No matching new advertisement for the three August forecasts was confirmed in the inspected calendar.

## Assistance and boundaries

Gemini 3.8 Flash independently confirmed the NJDOT season definition. Its NJ TRANSIT URL retrieval returned an incomplete page shell; its absence findings were not accepted. Chrome and PDF extraction supplied the transit evidence.

This report describes source checks and local code behavior, not deployment or refreshed production data. Publication requires CI, data refresh review, and live verification. No dates or cancellations were inferred from search-result absence.

Deployment blocker found: the configured NJ TRANSIT parser currently receives a calendar shell and returns zero records although Chrome loads the calendar. A new guard makes that an explicit failed refresh. The PDF parser succeeds independently, but this does not establish a complete source refresh. Do not deploy this as a completed transit reconfirmation or hand-edit production JSON to work around the retrieval problem.

September 6 resolution: the full calendar HTML is embedded in the official page's Nuxt JSON payload. The parser now resolves only the record with the calendar slug and title, without executing JavaScript. A live read returned two open solicitations (0000162 and 0000238) plus five forecasts. Missing/malformed calendar payloads and failed forecast document retrievals raise errors instead of reporting a successful partial refresh.
