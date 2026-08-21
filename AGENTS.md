# NJ Transportation Bids Agent Guide

## Mission

Build a trustworthy public index of open and upcoming New Jersey transportation
construction and professional-services opportunities. Contractors, suppliers,
subcontractors, and consultants may rely on this data to decide where to spend
estimating time. Accuracy, provenance, freshness, and explicit uncertainty matter
more than maximizing record count.

The public site is `https://www.njtransportationbids.com`.

## Runtime Truth

- The deployed application is Flask, served by Gunicorn from `app.main:app`.
- Render builds the root `Dockerfile` and auto-deploys `main`.
- Production sets `DATA_BACKEND=file`. A PostgreSQL database is provisioned, but it
  is not the canonical public data path.
- Public opportunity pages read `data/notices/notices.json` through
  `app/main.py::load_public_opps()`.
- `data/opportunities.json` and database `opportunity_leads` are legacy fallbacks.
  Do not redirect public pages to them without an explicit migration plan.
- The GitHub Actions crawler writes generated data back to `main` as `crawl-bot`.
  Expect `main` to advance after crawler changes are pushed.

## Canonical Data Pipeline

1. Source configuration: `crawlers/notice_sources.py::NOTICE_SOURCES`.
2. Source parsers: `crawlers/notice_crawlers.py`.
3. Orchestration, lifecycle, noise filtering, and persistence:
   `crawlers/notice_runner.py`.
4. Canonical records: `data/notices/notices.json`.
5. Per-source history: `data/notices/crawl_log.json`.
6. Evaluated health snapshot: `data/notices/health_summary.json`.
7. Public loading and display: `app/main.py`, `app/notice_routes.py`, and
   `app/templates/`.

At the time this guide was written, `NOTICE_SOURCES` contains 47 configured sources:
17 state/regional, all 21 counties, 7 municipal, and 2 procurement platforms. Treat
those numbers as a snapshot and calculate current counts from configuration.

## Non-Negotiable Data Rules

- Preserve official source text and the official URL. Normalized fields supplement
  source data; they never replace or erase it.
- Publish only transportation construction, heavy civil/infrastructure, and relevant
  professional services. General goods and unrelated procurement are out of scope.
- Include narrowly targeted road-operations materials and components such as rock
  salt, snow-plow parts, and traffic-control devices for the supplier audience.
  Exclude general commodities and fleet maintenance or vehicle-repair contracts.
  Until a dedicated supplier category exists, classify included items as construction.
- Distinguish `open`, `upcoming`, `expired`, `noise`, and unresolved/review states.
- Never infer counties from directional contract packaging such as North, Central,
  or South.
- Never use naive county substring matching. Place names such as Ocean City, Union
  City, Gloucester City, and the Henry Hudson Trail are known traps.
- Use `app/core/geography.py` for county normalization. Preserve `county` as raw input
  and use `counties`, `coverage_scope`, `region_raw`, `geography_confidence`, and
  `geography_evidence` for normalized output.
- County filters may use only explicit notice text or a structured county field from
  an official source record. An agency's jurisdiction is a non-authoritative
  `agency_county_hint`, not county-level evidence.
- Bi-state authority records keep `BISTATE` scope and an empty normalized county list;
  do not expand agency jurisdiction into New Jersey counties.
- Use `app/core/deadlines.py` for deadline parsing. Preserve `due_date_raw`; store exact
  instants in UTC, render explicit Eastern time, label assumed time zones, and never
  invent a time for date-only records.
- A successful zero-result crawl is not automatically a failure. Source policy such
  as `allow_empty` determines whether zero is expected.
- A green workflow only proves execution. Verify record counts, representative known
  opportunities, health output, and public rendering.

## Record Identity and Lifecycle

- Parser-generated IDs are hashes of `source_id`, title, and the contract number or
  official URL. They are implementation identifiers, not agency-issued identity.
- Merge updates exact ID matches and preserves manual overrides. A record missing from
  a successful authoritative current-listing crawl is marked `source_inactive`; a
  failed or non-authoritative partial crawl must not retire it.
- Dedupe prefers active records and then newer `crawled_at` values. It collapses, in
  order, exact IDs, equal `(source_id, contract_number)` pairs, and equal
  whitespace/case-normalized titles within one source.
- An amended listing with the same source and contract number therefore resolves to
  the newest active record. Do not assume this safely models an agency that reuses a
  contract number for a distinct procurement cycle.
- Any identity-rule change requires fixtures for amendments, reissues, reused contract
  numbers, title changes, source removal, and failed refreshes. Preserve traceability
  from the retained record to the official listing.

## Repository Map

- `app/main.py`: Flask app, canonical public routes, SEO, exports, source ledger,
  calendar output, and legacy admin routes.
- `app/notice_routes.py`: public notice views and notice CSV export.
- `app/core/`: pure normalization and filtering logic. Prefer this layer for reusable,
  deterministic business rules.
- `app/templates/`: public and admin Jinja templates.
- `crawlers/notice_sources.py`: configured source inventory and crawl policy.
- `crawlers/notice_crawlers.py`: source-specific retrieval and parsing.
- `crawlers/notice_runner.py`: crawl entry point, merge, lifecycle, dedupe, health, and
  generated JSON writes.
- `crawlers/source_health.py`: source-health evaluation and county coverage.
- `data/notices/`: crawler-generated canonical data. Do not hand-edit it to simulate a
  parser fix.
- `reports/`: generated analysis outputs, not runtime inputs.
- `.github/workflows/crawl.yml`: daily/weekly Actions schedule and bot commit step.
- `render.yaml`, `Dockerfile`, `Procfile`: deployment configuration.
- Root modules and directories outside `app/` and `crawlers/` contain an older
  registry architecture. Confirm whether code is reachable before changing it.

## Development Commands

Use Python 3.11 and run commands from the repository root.

```bash
pip install -r requirements.txt
python -m unittest -v test_deadlines test_geography test_notice_pipeline test_parsers
python -m compileall -q app crawlers
gunicorn app.main:app --bind 0.0.0.0:10000
```

On Windows, use the same `python -m ...` commands in PowerShell. A Docker option is
also available:

```bash
docker compose up --build
```

Useful crawler commands:

```bash
python crawlers/notice_runner.py --source state-njdot-construction --dry-run
python crawlers/notice_runner.py --tier 1 --dry-run
python crawlers/notice_runner.py --weekly --strict-health
```

Important: crawler `--dry-run` prevents writing `notices.json`, but source crawl log
entries are still recorded, and later health evaluation reads that log. It does not
regenerate `health_summary.json` itself. Use an isolated worktree when validating
crawler changes, and use a clean production crawl for publishable health evidence.

## Testing Reality

- The focused suite above covers the current public crawler, geography, deadline,
  source-health, SEO, export, and calendar paths.
- `python -m unittest discover` currently also finds three legacy tests that import
  absent package paths: `app.services.dedupe`, `app.services.promoter`, and
  `app.core.scoring`. Do not report a completely green discovery run unless those
  legacy imports have been repaired.
- Add a regression test before or with every parser, lifecycle, geography, deadline,
  source-health, or public-route fix.
- Parser fixtures should include both a true positive and a plausible false positive.
- Test timezone behavior with aware UTC values, explicit Eastern values, naive local
  values, date-only values, and anticipated windows.

## Safe Change Workflow

1. Fetch `origin/main` and work in an isolated branch/worktree.
2. Inspect the current file and adjacent call sites; do not trust stale architecture
   documents or old root modules over runtime imports.
3. Make the smallest coherent end-to-end change.
4. Run focused tests, compile checks, `git diff --check`, and Flask test-client smoke
   checks for affected routes.
5. Review generated-data diffs separately from source-code diffs.
6. Before pushing directly to `main`, fetch again and ensure `origin/main` is the
   expected parent. Crawl-bot commits may have advanced it.
7. If crawler code changed, monitor the triggered `Daily notice crawl` through
   completion and inspect failed job logs rather than only rerunning.
8. Verify Render's public domain with cache-busting requests. Check representative
   pages, CSV fields, and calendar output when relevant.

## Editing Constraints

- Do not revert unrelated or user-authored changes in a dirty worktree.
- Do not hand-edit generated notice JSON as the fix for crawler behavior.
- Do not commit local `data/network/` files created by importing network modules unless
  that data is explicitly part of the task.
- Never commit credentials, `.env`, admin passwords, cookies, or connector tokens.
- Keep raw source evidence and add normalization metadata instead of silently
  correcting source values.
- Treat crawler errors as data-quality incidents. Prefer an honest error state over a
  healthy badge backed by stale or unrelated records.

## Definition of Done

A change is complete only when:

- The behavior is implemented in the canonical runtime path.
- Relevant regression tests pass.
- No unrelated files are included.
- Generated data is refreshed when the schema or enrichment output changed.
- GitHub Actions succeeds when affected.
- The Render-hosted public behavior is verified, not merely assumed from deployment.
- Remaining uncertainty, inaccessible sources, and known testing gaps are stated.

## Two-Agent Collaboration

- Claude Web is the research, audit, adversarial-review, requirements, and test-design
  partner. Its conclusions must be bounded by the files and web evidence supplied.
- Codex is the repository, implementation, local execution, GitHub Actions, Render,
  and live-verification partner.
- Do not have both agents independently perform the same exploration or implementation.
- Claude should return the handoff contract in `docs/CLAUDE_WEB_HANDOFF.md`. Codex should
  validate its evidence against the current repository before editing.
