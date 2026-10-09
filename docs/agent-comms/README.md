# Agent comms

An asynchronous notepad between the two agents working on this site: **Claude**
(cloud sessions, repository access over git) and **Codex** (local, runs and
verifies the site on the owner's machine).

## Why it lives in the repository

It has to be somewhere both agents can actually reach. Codex runs on the
owner's machine and can see local folders; Claude runs in an isolated cloud
container with no access to that machine's filesystem. Git is the only
filesystem the two share, so the notepad is a repository file and syncs on
push/pull.

This is not live chat. A note is visible to the other agent only after it is
pushed and the other side fetches.

## Rules

- **One file per agent. Write only your own.** `claude.md` is Claude's,
  `codex.md` is Codex's. Never edit, reword, reorder, or delete an entry in the
  other agent's file — if you disagree, answer in your own file and reference
  the entry's date and heading. One file per agent also means two agents writing
  at once cannot produce a merge conflict.
- **Append at the top.** Newest entry first, under a `## YYYY-MM-DD — subject`
  heading, so the current state is readable without scrolling.
- **Say what is evidence and what is a hypothesis.** Same discipline as the rest
  of the project. If you did not verify it, label it.
- **Close your own items.** When an entry is resolved, add a new entry saying so
  rather than editing the old one. The history is the point.
- **Keep decisions out of here.** This is a working channel. Anything that
  becomes a durable rule belongs in `AGENTS.md` or `docs/TIME_AND_TOOLS.md`;
  anything that becomes work belongs in a commit or a pull request.

## Division of labour

Recorded here because it determines who can close which item:

| | Claude | Codex |
|---|---|---|
| Repository read/write | yes, over git | yes, local |
| Run the test suite | yes | yes |
| Fetch external sites (agency pages, the live site) | **no** — egress proxy blocks them | yes |
| Verify Render deployment | **no** | yes |
| Inspect the live DOM / screenshots | only from what the owner pastes | yes |

So any item that needs a live page fetched, a deployment confirmed, or an
agency portal inspected is Codex's to close. Claude's side is repository
evidence, data audits, extraction logic, tests, and written reasoning.
