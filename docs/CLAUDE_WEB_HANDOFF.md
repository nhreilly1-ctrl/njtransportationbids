# Claude Web Handoff: NJ Transportation Bids

## How the Owner Uses This File

Upload this file and the task-specific evidence to Claude Web at the start of a new
conversation. Do not upload the entire repository by default. Add only the CSV, PDF,
HTML capture, screenshots, or source files needed for the current analysis.

After Claude completes the analysis, bring its `CODEX HANDOFF PACKET` back to Codex.
Codex will check the current repository, implement the change, run tests, deploy, and
verify production.

## Project Scenario

NJ Transportation Bids is intended to become a trustworthy, one-stop public index of
New Jersey transportation construction and professional-services opportunities. The
site serves contractors, subcontractors, suppliers, engineers, and consultants. The
underlying public procurements can represent billions of dollars, so confident wrong
answers are more harmful than explicit uncertainty.

The application aggregates official agency information. It is not the issuing agency
and must direct users back to official notices for submission requirements and addenda.

## Current Engineering Baseline

The following was verified on 2026-08-20. Treat mutable counts and health as a snapshot.

- Production site: `https://www.njtransportationbids.com`.
- Application: Flask/Gunicorn on Render.
- Public canonical records: `data/notices/notices.json`.
- Canonical source configuration: `crawlers/notice_sources.py`.
- Source inventory snapshot: 47 sources, including all 21 NJ counties.
- Daily/weekly crawling: GitHub Actions workflow `.github/workflows/crawl.yml`.
- County normalization: `app/core/geography.py`.
- Deadline and timezone normalization: `app/core/deadlines.py`.
- Public Sources page reads configured sources plus crawl health, not only sources that
  happened to return records.
- Deadline source text is preserved while normalized UTC/Eastern fields are added.
- Record identity and lifecycle behavior is documented once in the `Record Identity
  and Lifecycle` section of `AGENTS.md`; do not restate or guess it from an export.
- Current crawl health must be read from `data/notices/health_summary.json`; never rely
  on a health count quoted in an old conversation.

## Claude's Best Role

Claude Web should maximize work that can be completed from supplied evidence without
local execution:

- Research official agency procurement pages and document access patterns.
- Audit CSV/JSON exports for missing, duplicated, stale, mistagged, or conflicting data.
- Read procurement PDFs and extract evidence-backed fields.
- Design adversarial parser fixtures and acceptance criteria.
- Review UX copy, information architecture, source disclosures, and trust language.
- Compare a public page with an official source and produce a bounded discrepancy list.
- Analyze county, category, deadline, and scope taxonomies.
- Review current source files supplied by the owner and identify risks before Codex edits.

Claude Web should not spend time pretending to perform work that requires the local
repository, Git history, Actions logs, Render state, credentials, or live browser session.

## Evidence Rules

- Separate `OBSERVED` facts from `INFERRED` conclusions and `HYPOTHESIS` items.
- Every record-level finding must include a traceable ID, URL, source field, quotation,
  or document page number.
- State which files and versions were actually provided.
- Do not say a defect exists "in the repo" unless the relevant current code was supplied.
- Do not label live-site scraping as repository analysis.
- Do not recommend broad geographic inference from North/Central/South contract labels.
- Preserve raw official values in every proposed schema or parser design.
- Audit lifecycle values against the explicit states in `AGENTS.md`; do not merge open,
  upcoming, expired, inactive, noise, and review states into one generic active flag.
- Evaluate zero-result sources against the current source configuration's `allow_empty`
  policy. Zero with `allow_empty=true` may be healthy; zero without it is a defect
  signal, not proof that no opportunities exist.
- Treat health evidence produced after a local `--dry-run` as potentially perturbed.
  Dry-run updates `crawl_log.json` but not `health_summary.json`; later health evaluation
  consumes that log. Ask for a clean production crawl when health provenance matters.
- Flag inaccessible/paywalled/JavaScript-blocked sources rather than inventing coverage.

## What to Ask For

Ask only for the minimum evidence needed. Prefer one short request from this list:

- Record audit: CSV/JSON export with identity and lifecycle fields (`id`, `title`,
  `source_id`, `source_name`, `contract_number`, `official_url`, `status`,
  `source_status`, `source_inactive`, `noise_flagged`, `is_planned`); raw and normalized
  geography pairs (`county`, `counties`, `coverage_scope`, `region_raw`,
  `geography_confidence`, `geography_evidence`); and raw and normalized deadline pairs
  (`due_date_raw`, `due_date_parsed`, `deadline_at`, `deadline_local`,
  `deadline_timezone`, `deadline_timezone_source`, `deadline_timezone_assumed`,
  `deadline_precision`, `deadline_display`). Request only the applicable subset, but
  never audit a normalized value without its raw counterpart and provenance fields.
- Source-health audit: relevant `NOTICE_SOURCES` entries including `id`, `crawl_freq`,
  `critical`, `allow_empty`, and parser policy, plus `crawl_log.json` and
  `health_summary.json` from a clean production crawl.
- Parser review: current source configuration entry, parser function, representative
  official HTML/API/PDF fixture, and existing tests.
- UX review: public URL or screenshots plus the user goal for the page.
- PDF extraction: the PDF plus the desired fields and confidence policy.
- Architecture review: `AGENTS.md` plus only the current modules involved.

If the evidence is insufficient, produce the useful evidence-independent portion and
name exactly what remains unverifiable.

## Required Output Contract

End every implementation-oriented response with this exact structure:

```text
CODEX HANDOFF PACKET

Objective:
One sentence describing the user-visible or data-quality outcome.

Evidence supplied:
- Exact filenames, URLs, record IDs, document pages, or source snippets reviewed.

Observed findings:
- Ordered by severity. Each finding includes traceable evidence.

Inferred conclusions:
- Conclusions logically derived from observed evidence but not directly stated by it.

Hypotheses:
- Plausible explanations that require repository, source, or runtime verification.

Recommended behavior:
- Specific rules and expected outputs, not implementation claims.

Acceptance tests:
- Input -> expected output.
- Include true positives, false positives, and failure behavior.

Likely repository touchpoints:
- Only files confirmed from AGENTS.md or supplied in the task.
- Mark uncertain paths as hypotheses.

Risks and non-goals:
- Data-loss, false-positive, stale-source, timezone, geography, or deployment risks.

Unverified assumptions:
- Anything Codex must confirm against the current repository or environment.
```

Do not include a unified diff unless the exact current file contents were supplied and
the owner explicitly asks for one. Even then, the handoff packet remains required.

## Starter Prompt for Claude Web

Paste the following after uploading this file:

```text
You are the research, audit, requirements, and adversarial-review partner for NJ
Transportation Bids. Read the attached Claude Web handoff and follow its evidence rules.
You do not have repository or deployment access unless I explicitly provide files or
outputs. Do not claim implementation or repository facts that you cannot verify.

For this task, do as much evidence-backed analysis as possible, minimize questions, and
end with the exact CODEX HANDOFF PACKET contract so Codex can validate and implement it.

Task: [REPLACE WITH THE CURRENT TASK]
```

If the `Task` value is blank or still contains bracketed placeholder text, state that
no task was supplied, make no task-specific or repository claims, provide only useful
evidence-independent orientation, and request the missing objective.

## Efficient Task Patterns

### Official Source Investigation

Provide the official source URL and ask Claude to identify access method, active-status
signals, deadline fields, pagination, detail-page requirements, false positives, and a
small fixture matrix. Codex then inspects the current parser and implements only the
verified delta.

### Dataset Audit

Export only the fields needed, ask Claude for an evidence CSV or structured findings,
but keep each audited raw value paired with its normalized value, confidence/provenance,
and lifecycle state. Require counts by defect rule. Codex then maps each rule to current
normalization code and writes regression tests before retagging records.

### PDF Review

Upload the official PDF, ask for page-cited extraction and uncertainty labels, and have
Claude distinguish binding deadline text from pre-proposal dates, issue dates, addenda,
and descriptive project schedules.

### UX and Value Review

Give Claude the public URL/screenshots and a specific user persona. Ask for prioritized
friction, trust, and decision-value findings. Codex then checks feasibility against the
actual templates and implements the selected changes.

## Avoid Duplicate Spend

- Do not ask Claude and Codex to independently audit the same material.
- Do not ask Claude to guess the current parser and then ask Codex to rediscover the
  problem. Give Claude the relevant parser only when code-level review is useful.
- Do not send Codex an unstructured transcript. Send the final handoff packet.
- Do not ask Codex to implement every idea. Select the highest-value objective first.
- Reuse this file in each new Claude Web conversation; update its dated baseline when
  architecture changes materially.
