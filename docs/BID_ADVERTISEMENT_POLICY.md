# Advertised opportunities and closing dates

Owner direction, October 28, 2026: publish opportunities when discovered even
when no closing date is known. Remove them from active boards when a complete,
successful agency-listing check establishes that they are no longer advertised.
Keep the detail URL as a clearly closed reference page.

Deadline quality and publication are independent. A missing date is labelled
“No known closing date.” A conflicting or unreadable document remains published
and appears in the Closing date review filter. Neither gets an invented calendar
deadline. Forecasts remain in Upcoming while advertised, with old or ambiguous
expected windows flagged as needing an update.

## Which date controls

The current linked official bid advertisement controls over the agency's table,
calendar or Open badge. A newer ordered addendum controls over its predecessor.
This applies to NJ TRANSIT as well as other agencies. A document must match the
solicitation identity and contain an explicit submission-date statement.

Version order comes from a published addendum number or an explicit issue date.
The order records were fetched and the latest *closing date* do not establish
which document is newest. Ambiguous versions, identity mismatches, inaccessible
new versions and uncertain extraction require review. A failed recheck of the
same links retains the last verified document and discloses the failure; a new
unreadable link cannot silently fall back to the old document.

`due_date_raw` retains the agency listing text. `effective_deadline_raw`,
`deadline_basis` and `deadline_source_url` identify the displayed date. The
`bid_document_review` packet preserves checked links, source version evidence,
hashes, exact deadline excerpts, pages, identity checks and selection outcome.
Both CSV exports carry the effective date and its provenance. A document change
or closing-date change is recorded in material change history.

## Complete checks and outages

Structured current-listing parsers retain their existing retirement contract.
HTML fallback sources can attest completeness only when a recognized listing
loads without pagination/deferred results and has records or an explicit empty
state. Partial, failed, unrecognized or unexpected-empty checks cannot retire
records. Their coverage limitations remain visible in source health.

NJ TRANSIT's calendar also contains historical events. Past rows are retained
as past calendar events; a matching document establishing a later deadline can
reopen them. Merely encountering an archived calendar row does not make it Open.
Historical calendar entries cannot suppress a newly published forecast. Both
PDF and Word forecast documents are supported. A linked but unsupported,
unreadable or structurally changed forecast document makes the source check
incomplete, preventing that check from retiring existing forecasts.

Document checking currently reads at most four PDF pages and six linked documents
per opportunity. Unsupported or unreadable documents stay in review. A review
flag describes an evidence gap, never a reason to suppress an advertised listing.
