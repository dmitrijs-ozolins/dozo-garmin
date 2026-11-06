# ADR 0001: Remote task execution via GitHub issues and Claude Code action on a self-hosted Mac mini runner

- **Status:** Accepted
- **Date:** 2026-11-06
- **Deciders:** Dmitrijs Ozolins

## Context

Development of this repo should be drivable from a phone: post a task,
have it implemented on the dedicated Mac mini, and get a pull request back
for review.

The Mac mini is also becoming the runtime for the Garmin sync and calendar
automation (see [AUTOMATION_PLAN.md](../AUTOMATION_PLAN.md)), so it holds
the local Garmin session token, `.env` with `DATABASE_URL`, and
`past_workouts/`. Tasks that touch the sync need that local access to be
verified against real data (e.g. a `--dry-run` against the real Garmin
calendar).

The repo is public on purpose: it's a place to practise, in the open, the
engineering workflow used in business projects, end to end.

## Options considered

1. **Claude Code on the web (cloud sessions).** Start a task from the
   Claude app; it runs in Anthropic's cloud and pushes a branch for a PR.
   Zero setup, works when the mini is off, but has no access to the
   mini's token, database or local files, so it can't verify against real
   data.
2. **Remote Control.** A long-running `claude remote-control` session on
   the mini, driven from the phone. Full local access and interactive, but
   it's one live session, not a task queue — remote pair-programming
   rather than fire-and-forget.
3. **GitHub issue → `anthropics/claude-code-action` on a self-hosted
   runner on the Mac mini.** Open an issue (GitHub mobile app) mentioning
   `@claude`; the workflow runs on the mini, implements the task on a
   branch and opens a PR linked to the issue. Iterate by commenting
   `@claude ...` on the PR.
4. **Custom Telegram bot pipeline.** A launchd poller on the mini reads
   bot messages, runs `claude -p` in a git worktree and calls
   `gh pr create`. Reuses the existing bot, but all the plumbing (queue,
   timeouts, failures, PR iteration) is hand-built and maintained.

## Decision

**Option 3.** Tasks are GitHub issues; `anthropics/claude-code-action`
runs on a self-hosted GitHub Actions runner on the Mac mini and delivers
the result as a pull request.

Reasons:

- It exercises the full, standard flow — issue → branch → PR → review →
  merge — which is the point of this repo as a skills playground.
- Issues are a real backlog: tasks queue up, are traceable, and link to
  their PRs.
- It runs on the mini, so it has the same local access the automation
  needs.
- It's extensible within the same flow. Planned next step: an analysis /
  discussion stage before implementation (e.g. Claude first comments a
  proposed approach on the issue, implementation starts only after
  approval). That fits naturally as additional workflow triggers or
  labels.

## Consequences

- **Setup required on the mini:**
  - GitHub Actions self-hosted runner installed as a launchd service.
  - `CLAUDE_CODE_OAUTH_TOKEN` repo secret (from `claude setup-token` on
    the mini), so runs use the Claude subscription rather than an API key.
  - A workflow in `.github/workflows/` triggered by issue / comment events
    with `contents`, `pull-requests` and `issues` write permissions.
- **The mini must be always on** — same requirement as the sync
  automation (`pmset` no-sleep + autorestart, auto-login, FileVault
  trade-off), so it's set up once for both.
- **Self-hosted runner on a public repo — required hardening.** The public
  repo is intentional; these guards are part of the setup, not a reason
  against it:
  - Gate every job on the triggering user:
    `if: github.actor == 'dmitrijs-ozolins'`.
  - Repo Settings → Actions: require approval for workflows from all
    outside contributors.
  - Never run self-hosted jobs on `pull_request` events from forks.
  - Optionally run the runner as a separate macOS user without read access
    to `~/.dozo-garmin`, granting access deliberately where a task needs
    it.
- Every change arrives as a PR, so review and merge stay manual.
- Options 1 and 2 remain available ad hoc (cloud session when the mini is
  down and the task is code-only; Remote Control for live steering)
  without changing this decision.
