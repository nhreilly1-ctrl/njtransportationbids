# Time and Tools — the product concept

This is the settled UX concept for njtransportationbids.com. It is binding on
public-facing changes. When a design argument cannot be resolved by taste, it is
resolved here.

## The concept

A contractor deciding where to spend estimating time is spending two scarce
things: **hours** finding and reconstructing what a project actually is, and
**readiness** to act once they have found it. This site sells both back.

Every public page has two jobs, in this order:

1. **Cut the time to understand the project.** The reader should know what the
   work is, where it is, when it closes, and who is letting it — without leaving
   the page, opening a PDF, or visiting a second portal.
2. **Hand over the tools to act on it.** The official document, the deadline in
   their calendar, the agency's rulebook, the comparable work, the location.

Everything else is decoration.

## The tone rule

**Explain the agency's process. Never explain the user's trade.**

The audience are professionals. They know what milling is, how to price a deck
replacement, and how to read a plan set. They may not know that NJDOT requires
prequalification before a prime bid, that the Turnpike Authority prequalifies
separately, or that the Port Authority does not run under New Jersey State
contracting rules at all. Institutional knowledge is in scope. Craft knowledge
is condescension.

This rules out: bidding tutorials, glossaries of construction terms, "did you
know" tips, progress-bar onboarding, and any copy that congratulates the reader
for clicking.

## Operating rules

1. **Every project page is a front door.** Search traffic arrives on individual
   opportunity pages, not the homepage. A project page must stand alone and must
   never assume the homepage was seen.

2. **Answer four questions above the fold: what, where, when, who.** If the
   record cannot answer one, print the absence in plain language ("County not
   stated in notice"). The reader must never be left guessing whether the site
   failed or the notice was silent.

3. **State facts; never make the reader compute.** Days remaining, corridors,
   counties, related counts, normalized deadlines — precompute all of it. The
   reader should never open a second tab to cross-reference something this site
   already holds.

4. **Uncertainty is stated, never hidden and never invented.** This is the data
   spine of the project, and it is also a time rule: a deadline the reader trusts
   is a deadline they do not re-verify. Trust is measured in minutes saved.

5. **Every tool is a verb aimed at the next action.** Open the official source.
   Add the deadline to a calendar. See it on a map. Check prequalification. See
   related work. If a control is not a plausible next action for *this* record,
   it is clutter, not a tool.

6. **Unique content outweighs shared content.** The project's own facts lead and
   dominate; navigation, resources, and site copy sit below them and stay
   subordinate. A page that is mostly boilerplate buries the thing the reader
   came for and reads as a near-duplicate to search engines.

7. **Precision where evidence supports it; the honest window where it does not.**
   "Closes Tuesday, Aug 25, 10:00 AM ET" when the notice says so. "Fall 2026"
   when the agency only committed to a season. Never manufacture a date to look
   precise, and never round a real one away.

8. **The two clocks stay separate.** Work that is open for bid and work an agency
   merely expects to advertise are different jobs on different timescales.
   Interleaving them costs time in both directions: it buries this week's
   deadlines and it hides the pipeline.

9. **No accounts, no gates, no email walls.** The moment the site costs a
   registration it costs more time than it saves — and every competitor it beats
   is a registration wall.

## How to test a change against this

**The two-minute test.** A qualified bidder landing cold on a project page should
be able to decide go / no-go within about two minutes, and reach the official
document in one click.

A change passes if it removes a step, removes a question, or removes a tab. A
change that adds a step must remove a larger one. "It looks better" is not a
passing argument; "it answers the where question without scrolling" is.

## What this is not

Out of scope, permanently, unless this document changes:

- Not an estimating or takeoff tool.
- Not bid preparation or document assembly.
- Not a CRM, a lead tracker, or a bidder network.
- Not a mirror of agency plan sets and PDFs — always link to the official copy.
- Not a source of bidding strategy or legal advice.

## Decisions this settles

| Question | Settled answer | Evidence |
|---|---|---|
| Is the anticipated pipeline a headline feature or a sidebar? | Headline. | 5 of 6 project-page search clicks were anticipated records; it is 58% of live inventory and effectively unpublished elsewhere in indexable form. |
| What happens to a project page when the bid closes? | Keeps its URL and shows a closed state. It does not 404 or disappear. | Rule 4 and rule 1: an indexed page that vanishes spends the reader's time and forfeits earned traffic. |
| What does "related" mean? | Evidenced overlap — shared corridor, county, or structure — not same-agency. | Rule 3: same-agency picks from a 70-record pool make the reader do the relevance work. |
| Do we show New Jersey State requirements on Port Authority and DRPA/DRJTBC records? | No. Withhold them and say why. | Rule 4: a requirement that does not apply is worse than no requirement. |
| How long may the resource pack be? | Long enough to carry the agency block plus any federal-aid set; short enough to stay below the project facts. | Rule 5 and rule 6. |

## Known gaps this concept implies but the data cannot yet serve

- **Project scale or value.** Nothing in the sources carries a reliable estimate,
  so the "is it my size" question stays unanswered. Do not infer one.
- **"New since you last looked."** Needs `first_seen_at`; `crawled_at` cannot
  answer it. Until then, do not badge anything as new.
