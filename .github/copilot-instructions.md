# Project instructions

Shared instructions for AI assistants working on this repo (GitHub
Copilot reads this file; Claude Code imports it from `.claude/CLAUDE.md`).

## What this is

Personal Garmin Connect automation: a daily sync of activities and
wellness data into Postgres, anomaly signals with Telegram alerts, and
pushing structured workouts from a half-marathon training plan to the
Garmin calendar. Python, `python-garminconnect`, Postgres, GitHub Actions,
moving to a dedicated Mac mini.

- [README.md](../README.md) — setup and how to run.
- [docs/PLAN.md](../docs/PLAN.md) — original design rationale.
- [docs/AUTOMATION_PLAN.md](../docs/AUTOMATION_PLAN.md) — current work:
  scheduled calendar updates from the Mac mini.
- [docs/adr/](../docs/adr/) — architecture decision records.
- [training_plan/](../training_plan/) — the plan, progress log, and
  [COACHING_RULES.md](../training_plan/COACHING_RULES.md).

## Public repo — data rules

This repo is public on purpose. Never commit (and flag in review):

- Health/personal data: activities, laps, wellness, injury details,
  planned-workout rows — these live in Postgres (`DATABASE_URL`).
- Credentials: Garmin session tokens (`*garmin_tokens*.json`), `.env`,
  Telegram tokens, PATs.
- Raw exports (`past_workouts/`, `data/`) — GPS tracks and per-second HR.

`training_plan/` is the deliberate exception: summary-level numbers only
(paces, HR bands, VO2max checkpoints). See
[ADR 0003](../docs/adr/0003-health-data-in-external-postgres.md).

## Conventions

- Repo root holds only `README.md` among documents; all other docs go in
  `docs/`.
- Every new architectural decision (new dependency, storage, runtime,
  auth, integration, workflow shape) gets a new ADR in `docs/adr/`
  (next number, never renumber) and a row in `docs/adr/README.md`. A
  replaced decision is marked `Superseded by ADR NNNN`, not deleted.
- Match the surrounding code: module docstrings explain *why* and link to
  PLAN.md / ADRs; type hints; `from __future__ import annotations`.
- Keep "detect" (`garmin_sync/signals.py`) separate from "decide" (plan
  adjustment) — [ADR 0005](../docs/adr/0005-separate-detection-from-plan-adjustment.md).
- Garmin login in automation resumes from a stored token, never a
  password login — [ADR 0004](../docs/adr/0004-token-only-garmin-session-in-automation.md).

## Workouts and training analysis

Anything that builds Garmin workouts, edits the training plan, or
analyses runs must follow
[training_plan/COACHING_RULES.md](../training_plan/COACHING_RULES.md)
(treadmill formats in km/h and time steps, no treadmill pace comparison,
bike watts by feel, progress-log procedure).

## Verifying changes

- Python 3.12 in `.venv`; `pip install -r requirements.txt`.
- Scripts that write to Garmin must support `--dry-run`; use it before
  any real run.
- Calls needing the Garmin token or the database only work on the
  machine that holds them (the Mac mini); say so rather than faking a
  verification.
