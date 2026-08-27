# Garmin Workout Data Plan

Two problems to solve:

1. **Historical backfill** — pull workout history from September 2024 through end of 2025 for a one-time analysis of workout structure (the analysis itself is a separate story).
2. **Ongoing automated sync** — continuously pull Garmin data so we can (a) analyze it and (b) adjust the training plan when a workout is missed or there's a bad sleep / injury signal.

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

That data is exactly what problem 2 needs (react to bad sleep, etc.), so Strava alone can't cover problem 2. It could be a ToS-clean source for the *activity/structure* half of problem 1, at the cost of running two integrations instead of one.

**Decision: use `garth` (+ `python-garminconnect`, built on top of it) as the single source for everything** — it gets activities *and* sleep/HRV/wellness data in one place, which we need anyway for problem 2.

### CAPTCHA / anti-bot wrinkle for GitHub Actions

Garmin's login increasingly triggers CAPTCHA/anti-bot checks for logins from datacenter IPs — GitHub Actions runners qualify. If the workflow tries a fresh username/password login every run, it will likely get blocked eventually. Mitigation, supported by `garth`:

- Log in **once, interactively, from a local machine** (handles MFA if enabled).
- `garth.save(dir)` persists the session — an OAuth1 token good for ~1 year, plus an OAuth2 token `garth` auto-refreshes.
- Base64 the saved session and store it as a GitHub Actions **encrypted secret** (e.g. `GARMIN_SESSION`).
- The workflow calls `garth.resume()` from the secret instead of logging in fresh — no password, no CAPTCHA, in the common case.
- Expect to redo the manual local login roughly once a year (or if Garmin revokes the token) — treat this as scheduled manual maintenance, not something to auto-recover in CI.

## Plan

### Phase 0 — Auth bootstrap (local, one-time)

- Install `garminconnect` (wraps `garth`).
- Log in locally, `garth.save()`, store the resulting session blob as a GitHub Actions secret (`GARMIN_SESSION`).
- Never put the raw Garmin password in CI — only the derived session token.

### Phase 1 — Historical backfill, Sept 2024–Dec 2025 (local, one-time, not CI)

- Script pages through `get_activities_by_date(start, end)` for the full range.
- For each activity, pull laps/splits (or the raw FIT file via `download_activity(..., dl_fmt=ORIGINAL)`) — summary alone loses the interval/lap structure needed for the workout-structure analysis; FIT gives second-by-second pace/HR plus lap markers.
- Store to a local SQLite DB or Parquet files (one table for activities, one for lap splits). This becomes the dataset for the separate analysis story, and the same schema the daily sync will append to later.
- No need to run this in CI — it's a single local run against ~16 months of history.

### Phase 2 — Daily automated sync (GitHub Actions, problem 2)

- Scheduled workflow: `schedule:` cron trigger + `workflow_dispatch` for manual runs.
- Each run: `garth.resume()` from the secret → fetch yesterday's activity(ies), sleep, HRV, resting HR, Body Battery, training status.
- Append to the same SQLite/Parquet store, commit back to the (private) repo via a bot commit — data volume is tiny (KB/day), so git-as-a-datastore is fine.
- Diff against a **planned-workout file** maintained in the repo (simple YAML/JSON) to flag: missed session, sleep score below threshold, resting-HR spike, etc.
- **Injury** isn't something Garmin can report — it needs manual input (e.g. an `injury-log.yaml` file or a labeled GitHub issue the workflow reads).
- Keep "detect an anomaly" separate from "decide how to adjust the plan" — the sync step should emit clean structured signals (missed / low-sleep / HR-spike / manual-injury-flag) for a later plan-adjuster module to consume.
- Notify on flags however is convenient — commit a status file, comment on an issue, or ping Slack/Pushover.

### Storage note

Keep the repo **private** — it will contain health data plus the session secret. A SQLite file committed by the workflow is the simplest option; only move to an external DB (e.g. Supabase/Postgres free tier) if git-as-storage is outgrown.

## Open follow-ups

- Sketch the actual repo layout (`fetch.py`, workflow YAML, DB schema).
- Or start with the Phase 1 backfill script first, since that unblocks the analysis story sooner.
