# Claude's notes

Claude writes only in this file. See `README.md` for the rules.

---

## 2026-10-09 — Defect in `counties_never_produced` (mine, from August)

**Evidence, not hypothesis.** `coverage.counties_never_produced` in
`health_summary.json` currently lists Essex and Union. Both are wrong, and the
cause is in code I wrote in August.

`evaluate_source()` derives `ever_produced` from the source's retained crawl
history plus `last_count`. That history is capped at 30 entries — today's window
is 2026-09-14 to 2026-10-09, about 25 days. Essex and Union both produced
records earlier (4 and 1 respectively, still present in `notices.json`, now
retired), but neither has a positive count inside the retained window, so they
read as never-having-produced.

So the field has quietly drifted from "this source has never returned a record"
to "this source has returned nothing in the last ~25 days," while still being
labelled and worded as the former. Atlantic, Hudson and Middlesex correctly
dropped off the list because they genuinely started producing.

The fix I am pushing alongside this note: treat the presence of any record for
that source in the notice set as durable proof it has produced, since
`build_health_summary()` already receives `notices`. Retained history then only
needs to answer the recency question. Not a rename — the field should mean what
it says.

Flagging it here rather than only in the commit because the number is quoted in
`reports/zero_record_county_audit_2026-08-23.md`, and because if you have been
reading the field as literal "never," two counties have been misreported to you.

## 2026-10-09 — Where things stand from my side

Checked `origin/main` at `0ef3ec1`. 409 records, 144 live. The August corridor,
relatedness and bid-readiness work is all on main and the daily crawl is writing
the location fields, so that pipeline is healthy.

Read through the last six weeks of your commits. The evidence discipline is
holding in them — "without inventing deadlines", "evidence-gated", "reviewed
structure destinations", "bounded trade vocabulary". Two in particular solve
things I had written down as unsolvable: #20 found an evidenced route to project
size, which I had recorded in `docs/TIME_AND_TOOLS.md` as a gap the data could
not serve, and #14 covers the cross-agency orientation case. If #20's approach
generalises, the "known gaps" section of that doc is out of date and should be
amended.

**Still open, and only you can close them** (my container's egress proxy blocks
both the live site and the county portals — I cannot fetch either):

1. **Gloucester and Hunterdon.** Still listed as never-producing, and unlike
   Essex/Union I believe that one is accurate. From the August audit: Gloucester's
   parser has no structural guard at all, so a redesigned page yields silent zero
   indefinitely — the same failure mode Somerset had. Hunterdon uses the generic
   fallback parser and requires transport keywords in the anchor text itself,
   which CivicPlus bid-schedule pages often do not have. Both need someone to
   open the live page and say whether anything is listed. If they are genuinely
   empty, mark them verified the way Warren was.
2. **Wage-rate routing.** `bid_readiness.py` already parses the funding evidence
   NJDOT publishes — `Funding: Federal` / `Funding: State` on anticipated
   records, `Federal Project No:` on construction notices. Nothing yet turns that
   into the right wage link per record. Federally funded should point at the
   SAM.gov determination, state funded at NJDOL. It is the highest-value thing
   left in the readiness pack and the evidence is already parsed.

**One thing deliberately not built.** The owner asked about embedding a chatbot.
My assessment: a grounded, retrieval-limited assistant over our own corpus is
defensible; an ungrounded one is not, because the obvious questions people would
ask it — prevailing wage, material prices — are exactly the ones we hold no data
for, and a confident wrong number on those costs a contractor real money. If a
chatbot comes up again, the prior conclusion was: answer the known questions on
the page first (item 2 above), since a correct link beats a generated number.
