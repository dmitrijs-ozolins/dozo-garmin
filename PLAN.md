# Garmin Workout Data Plan

**Goal: ongoing automated sync** — continuously pull Garmin data so we can
(a) analyze it and (b) adjust the training plan when a workout is missed or
there's a bad sleep / injury signal.

(Historical backfill was originally a second problem here — pulling
workout history from September 2024 onward for a one-time
workout-structure analysis. Dropped: that history was already obtained
independently via manual TCX export into `past_workouts/`, so there's no
scripted backfill to build.)

## Background: how Garmin API access actually works

Garmin doesn't publish a self-serve developer API for individuals. What exists is the **Garmin Connect Developer Program / Garmin Health API** — a B2B partner program. Companies like Strava, TrainingPeaks, MyFitnessPal, etc. sign a formal partnership agreement with Garmin to get access; there's no public signup page where you register an app and get a key for *your own* account the way you can with Strava, GitHub, or most normal APIs.

### How Garmin↔Strava works

1. You connect Garmin to Strava in Garmin Connect's "Connected Apps" settings.
2. Garmin becomes a registered *partner* and **pushes** a FIT file to Strava's ingestion endpoint server-to-server, automatically, every time your watch finishes syncing an activity.
3. Once it lands in Strava, Strava's own API (public, free, documented, OAuth2, ~1000 req/day) lets you pull your own activities and per-activity time-series streams (HR, pace, cadence, power, altitude).

Strava is a legitimate, documented **side door** to a subset of your Garmin data — but only **workout/activity data**, since that's all Garmin's partner push includes. It carries none of:

- Sleep stages/score
- HRV / overnight HR
- Body Battery / stress
- Training readiness/status

That's exactly what the plan-adjustment half of this needs (react to bad sleep, etc.), so Strava alone can't cover it.

**Decision: use `python-garminconnect` as the single source for everything** — it gets activities *and* sleep/HRV/wellness data in one place.

(Originally scoped around `garth` underneath it, per the upstream README at the time. `garth` is now deprecated — see [its maintainer's note](https://github.com/matin/garth/discussions/222) — and `python-garminconnect` (>=0.3) dropped it in favor of its own built-in token store. Functionally the same idea, simpler mechanics: see Phase 0 below.)

### CAPTCHA / anti-bot wrinkle for GitHub Actions

Garmin's login increasingly triggers CAPTCHA/anti-bot checks for logins from datacenter IPs — GitHub Actions runners qualify. If the workflow tries a fresh username/password login every run, it will likely get blocked eventually. Mitigation:

- Log in **once, interactively, from a local machine** (handles MFA if enabled).
- `python-garminconnect` persists the session as a small JSON token file (a refresh-token pair) that it can reload and auto-refresh.
- Store that token JSON as a GitHub Actions **encrypted secret** (`GARMIN_TOKENS`).
- The workflow resumes from the secret instead of logging in fresh — no password, no CAPTCHA, in the common case. Since the refresh token can rotate on use, the workflow re-uploads the refreshed token back to the secret after each run (via a scoped PAT), so the next run isn't left holding a stale one.
- Expect to redo the manual local login roughly once a year (or if Garmin revokes the token) — treat this as scheduled manual maintenance, not something to auto-recover in CI.

## Plan

### Phase 0 — Auth bootstrap (local, one-time)

- Install `garminconnect`.
- Log in locally (handles MFA), which writes the session token file.
- Store its contents as the `GARMIN_TOKENS` GitHub Actions secret.
- Never put the raw Garmin password in CI — only the derived session token.

### Phase 1 — Daily automated sync (GitHub Actions)

- Scheduled workflow: `schedule:` cron trigger + `workflow_dispatch` for manual runs.
- Each run: resume the Garmin session from the `GARMIN_TOKENS` secret → fetch yesterday's activity(ies), sleep, HRV, resting HR, Body Battery, training status.
- Diff against a **planned-workout record** to flag: missed session, sleep score below threshold, resting-HR spike, etc.
- **Injury** isn't something Garmin can report — it needs manual input.
- Keep "detect an anomaly" separate from "decide how to adjust the plan" — the sync step should emit clean structured signals (missed / low-sleep / HR-spike / manual-injury-flag) for a later plan-adjuster module to consume.
- Notify on flags however is convenient — commit a status file, comment on an issue, or ping Slack/Pushover.

### Storage note

The repo is **public**, so nothing sensitive goes into git:

- Activities, laps, wellness, signals, planned workouts, and the injury log live in an external Postgres database (Supabase free tier or similar), not committed.
- The Garmin session token lives only in the `GARMIN_TOKENS` GitHub Actions secret (auto-rotated by the workflow via a separate scoped PAT), never in git.
- The training plan itself (and its progress log/checkpoints) is the one thing deliberately committed and public — it's summary-level, not raw health data.
- Raw per-activity exports (`past_workouts/*.tcx`) stay local-only and gitignored — they carry GPS tracks and per-second HR.

See `README.md` for the concrete setup and current implementation status.

## Open follow-ups

- Plan-adjuster module: act on the `signals` table's anomaly detections (currently detection-only, by design).
- Notifications on new signals (Slack/Pushover) — not wired up yet.
- Verify `garmin_sync/wellness.py`'s field mappings against a real account's data once the daily sync has run for a while; several of them are best-effort against Garmin's undocumented API.
