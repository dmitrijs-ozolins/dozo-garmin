# ADR 0007: GitHub Issues + Projects as the task tracker

- **Status:** Accepted
- **Date:** 2026-11-08
- **Deciders:** Dmitrijs Ozolins

## Context

Every change — a manual commit on the laptop or an agent PR from the Mac
mini ([ADR 0001](0001-remote-task-execution-via-github-issues.md)) —
should carry a ticket number, the way business projects managed in a PM
tool do. In an AI workflow the ticket is also the agent's spec and the
record of what was done.

Small personal project: no extra spend, no extra system to maintain.

## Options considered

1. **GitHub Issues + Projects.** Free on all plans; already the agent's
   trigger in ADR 0001; native `#N` autolinks, `Closes #N`, PR ↔ issue
   linking; GitHub mobile app.
2. **Linear.** Best-in-class PM UX and agent integrations, but a second
   system next to GitHub, and the agent trigger would need Linear →
   GitHub sync. Worth it for a team, not one person and one repo.
3. **Jira.** Overkill.
4. **Redmine self-hosted on the mini.** Free, but needs installing and
   maintaining (Ruby, DB, upgrades), a hand-written poller for the
   agent, and loses GitHub's native linking and mobile app. Doesn't
   avoid a Claude login either — whatever runs the agent authenticates
   to Claude.

## Decision

**Option 1.** The issue number is the ticket number.

Conventions:

- **Every change has an issue.** Routine training-plan / progress-log
  updates use one long-lived issue (e.g. "Training plan & log updates")
  instead of a new issue each time.
- **Branch:** `<issue>-<short-slug>`, e.g. `42-sync-calendar`.
- **Commit subject:** ends with the issue ref, e.g.
  `Add calendar diff (#42)`. `.githooks/commit-msg` appends it from the
  branch name automatically and rejects commits with no ref on a branch
  without a number. Enable once per clone:
  `git config core.hooksPath .githooks`.
- **PR:** body contains `Closes #N` (or `Fixes` / `Refs`).
  `.github/workflows/pr-issue-link.yml` fails a PR without one.
- **Labels:**
  - type — `type:feature`, `type:bug`, `type:chore`, `type:analysis`
  - agent triggers — `agent:analyze` (post an approach / spec for
    review), `agent:implement` (implement and open a PR)
- **Board** (GitHub Projects, Status field): Backlog → Analysis → Ready
  → In progress → In review → Done. Built-in project workflows move
  closed issues / merged PRs to Done.
- **Issue templates** for feature, bug and analysis; each states goal,
  context, acceptance criteria and out-of-scope, so an issue is a good
  agent prompt even when written on a phone.
- **ADRs** link the issue/PR that produced them.

## Consequences

- No extra cost: Issues, Projects and Actions on a public repo are free;
  the self-hosted runner uses no paid minutes.
- **Agent triggers are labels, not board columns.** Projects owned by a
  user account don't emit workflow events, so moving a card can't start
  the agent; adding an `agent:*` label can. The board is the view, labels
  are the switches.
- PRs opened with the workflow's `GITHUB_TOKEN` don't trigger other
  workflows, so `pr-issue-link.yml` won't run on agent PRs; the agent
  workflow must put `Closes #N` in the PR body itself.
- Direct commits to `master` still need an issue ref (the hook enforces
  it); `--no-verify` is the deliberate escape hatch.
- Spec-driven development (Spec Kit) is planned as the `agent:analyze`
  stage, building on these conventions — separate ADR when adopted.
