# DRJTBC addendum check - September 7, 2026

Manual review, not an automated assurance about future amendments.

Official listing: https://www.drjtbc.org/professional-services/current/

## C-753A
https://www.drjtbc.org/wp-content/uploads/C-753AAddendumNo.01.pdf

Reviewed five pages. No meeting, question, or proposal-closing revision found.
Page AD1-5 corrects conflicting submission instructions: email submission plus six
hardcopies of technical and fee proposals in separate sealed envelopes, delivered
to the Scudder Falls Administration Building. Page AD1-1 requires signing and
attaching that page to the proposal. These are project-specific, not standing rules.

## CM-552A
https://www.drjtbc.org/wp-content/uploads/CM-552AAddendumNo.01.pdf

Reviewed four pages. No meeting, question, or proposal-closing revision found.
Page AD1-1 requires signing and attaching that page. Subsequent pages clarify
proposal page limits, references, qualifications, and staffing; AD1-4 removes the
Assistant Resident Engineer from the referenced resume list and updates standards.

## Implementation boundary
The parser now preserves each project's published addendum links and flags changes
to that list as material updates. Project pages link directly to the amendments
beside the schedule. No regex guesses modify deadline fields based on PDF dates.
The warning explicitly states that PDF contents are not automatically reconciled.
Same-URL PDF replacements are not detected by this link-only pass. Content hashing,
document version review, and conflict handling remain follow-up work before reliable
automated schedule reminders can claim amendment awareness.
