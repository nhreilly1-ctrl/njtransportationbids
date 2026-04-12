SOURCE_LEVELS = [
    "State/Authority",
    "County",
    "Municipality",
]

ENTITY_TYPES = [
    "State Agency",
    "Transportation Authority",
    "County",
    "Municipality",
    "Transit Agency",
    "Bi-State Authority",
]

VERIFICATION_STATUSES = [
    "Verified",
    "Partial",
    "Needs mapping",
    "Unknown",
]

SOURCE_STATUSES = [
    "Pinned",
    "Fallback",
    "Inactive",
]

WEBSITE_READY_VALUES = [
    "Yes",
    "Partial",
    "No",
]

PARSER_HINTS = [
    "Portal listing",
    "HTML page",
    "Notice page",
    "PDF notice",
    "Calendar",
    "Manual review",
]

REFRESH_CADENCES = [
    "Daily",
    "Weekly",
    "Biweekly",
    "Monthly",
    "As needed",
]

OPPORTUNITY_STATUSES = [
    "Open",
    "Verify",
    "Closed",
    "Awarded",
    "Archived",
    "Open / Upon Contract",
    "Unknown",
]

RUN_STATUSES = [
    "success",
    "partial_success",
    "failed",
    "skipped",
]

CRAWL_STAGES = [
    "notice_discovery",
    "verify_and_extract",
    "recheck_live",
    "archive_pass",
]

TRIGGER_TYPES = [
    "scheduled",
    "manual",
    "retry",
    "backfill",
]

PROMOTION_DECISIONS = [
    "Promote",
    "Hold",
    "Reject",
    "Review",
]

ARCHIVE_REASONS = [
    "expired",
    "closed",
    "awarded",
    "cancelled",
    "duplicate_merged",
    "manual_removal",
]
