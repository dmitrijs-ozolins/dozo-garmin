# ADR 0003: Health data in external Postgres, not in the public repo

- **Status:** Accepted
- **Date:** 2026-08-27, revised 2026-09-22 (recorded retroactively 2026-11-06)
- **Deciders:** Dmitrijs Ozolins

## Context

The repo is public on purpose (see
[ADR 0001](0001-remote-task-execution-via-github-issues.md)). The synced
data — activities, laps, wellness, injury log, planned workouts — is
personal health data and must never be committed.

## Options considered

1. **SQLite file committed to git** (the original sketch in
   [PLAN.md](../PLAN.md)). Zero infrastructure, but publishes health data
   in a public repo.
2. **YAML files in the repo** for planned workouts and injury flags (also
   in the original sketch). Same problem for injury details.
3. **External Postgres** (Supabase free tier or similar) reached via
   `DATABASE_URL`.

## Decision

**Option 3.** All synced and personal data lives in external Postgres:
activities, laps, daily wellness, signals, sync-run history, planned
workouts and the injury log (managed via `scripts/plan_cli.py`).

Deliberate split of what goes where:

| Data | Location |
|---|---|
| Activities, laps, wellness, signals, planned workouts, injury log | Postgres |
| Garmin session token, Telegram credentials | Secrets / local files outside the repo |
| Raw TCX exports (`past_workouts/`) — GPS tracks, per-second HR | Local disk, git-ignored |
| Training plan, analysis, progress log (`training_plan/`) | Repo — deliberately public, summary-level numbers only |
| Code, schema, workflows | Repo |

## Consequences

- An external dependency (DB availability, free-tier limits) and a
  `DATABASE_URL` secret wherever the sync runs.
- Every table keeps a `raw` JSONB column with the untouched Garmin
  response; typed columns are best-effort and `raw` is the source of truth
  (see [ADR 0002](0002-python-garminconnect-as-single-data-source.md)).
- Anything new added to the repo must be checked against this split
  before committing.
