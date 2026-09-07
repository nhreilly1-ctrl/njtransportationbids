# DRJTBC document fingerprints

Pilot: DRJTBC professional-services RFPs and published addenda only. The normal
source update retrieves PDF bytes, then the merge compares SHA-256 fingerprints
by exact document URL. No PDFs or credentials are stored in the repository.

- First successful retrieval establishes a baseline, not a detected change.
- Unchanged files do not reset material-change timestamps.
- Failed checks preserve the prior successful hash and its timestamp; UI reports
  check unavailable. Recovery compares against that retained baseline.
- Same-URL byte changes record the previous hash and detection timestamp and flag
  the opportunity for review. The flag persists for that currently listed document;
  a successful unchanged retrieval does not establish that anyone reviewed it.
- Different URLs establish new baselines; existing addendum-list change tracking
  remains separate. Removed URLs are no longer compared.
- No dates, terms, attendance rules, or calendar events are inferred or changed.
  PDF metadata-only updates can change a fingerprint too.

Retrieval is limited to HTTPS DRJTBC /wp-content/uploads/ PDF URLs, no redirects,
10 MiB per document, bounded connect/read timeouts and elapsed streaming time,
and at most 24 unique document requests per source refresh. Unsupported URLs,
oversized downloads, redirects, HTTP errors and non-PDF responses are unavailable
checks, not replacements. Source listing success is independent of document access.

Verified September 7, 2026: all eight PDFs for C-753A, CM-552A, CM-816A and CM-809A
returned successful fingerprints. This is not a claim about document completeness
or substantive changes. Production requires an initial source refresh to establish
baselines; changes before that baseline cannot be detected retrospectively.
