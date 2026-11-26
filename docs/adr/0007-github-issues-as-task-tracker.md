# ADR 0007: GitHub issues as the task tracker, with an issue reference in every commit

- **Status:** Accepted
- **Date:** 2026-11-26
- **Deciders:** Dmitrijs Ozolins

## Context

Work on this repo now comes from several places: the laptop, the Mac mini
agent driven from the phone over Remote Control
([MAC_MINI_SETUP.md](../MAC_MINI_SETUP.md)), and later the issue-triggered
workflow from [ADR 0001](0001-remote-task-execution-via-github-issues.md).
Much of it is small and recurring — training plan edits, progress-log
entries, pushing a week to Garmin — and done by an agent committing on its
own.

Without a shared tracker the history is a flat list of commits: it's not
visible which change belongs to which task, and agent commits can't be
traced back to the request that caused them. Since the repo is public and
meant to practise a standard engineering workflow, the tracker should be
the one a business project would use.

## Options considered

1. **No tracker, descriptive commit messages only.** Zero overhead, but no
   backlog and no link between a request and its commits.
2. **External tracker (Linear, Notion, a markdown TODO in the repo).**
   Separate tool or manual bookkeeping; doesn't link natively to PRs.
3. **GitHub issues, referenced from branches, commits and PRs.** Native
   linking (`#N` in a commit or PR shows up on the issue), works from the
   GitHub mobile app, and is what ADR 0001's workflow triggers on anyway.

How to make the reference reliable:

- a. Convention only — easy to forget, especially for agents.
- b. Server-side check (a PR status check on commit messages) — enforced
  for everyone, but only fails after the push, and needs a workflow.
- c. **Client-side `commit-msg` hook** in the repo — fixes the message at
  commit time, from the branch name, so nobody has to type it.

## Decision

**Option 3 with a client-side hook (c).**

- Every task is a GitHub issue. Recurring training work goes to the
  standing issue **#1 "Training plan & log updates"**; anything else gets
  its own issue.
- Branches are named `<issue>-<slug>`, e.g. `1-progress-log-p2w3`,
  `3-mac-mini-setup`.
- Every commit message references the issue as `(#N)`.
  [`.githooks/commit-msg`](../../.githooks/commit-msg) appends it to the
  subject from the branch name, leaves messages that already contain `#N`
  alone, and rejects commits on branches without an issue number.
- PRs say `Refs #1` for the standing issue or `Closes #N` for a specific
  one. Nothing is pushed to `master` directly.

## Consequences

- Each clone opts in once: `git config core.hooksPath .githooks`
  (part of [MAC_MINI_SETUP.md](../MAC_MINI_SETUP.md) step 4; do the same
  on the laptop).
- Committing directly on `master` is rejected by the hook unless the
  message carries a `#N` — intended, since `master` only changes through
  PRs.
- The hook is client-side, so a clone without `core.hooksPath` can still
  commit without a reference. A PR check on commit messages can be added
  later if that turns out to matter.
- Merge commits and `fixup!`/`squash!`/`amend!` commits pass through
  unchanged.
