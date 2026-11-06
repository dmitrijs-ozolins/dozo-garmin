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

There are two ways in:

- **`python-garminconnect`** (unofficial) — wraps the same internal
  endpoints the Garmin Connect web app uses. Covers everything this
  project needs: activities, wellness (sleep, HRV, Body Battery, training
  readiness/status) and **writes** — uploading structured workouts and
  scheduling them on the calendar. Downsides: undocumented, can break
  without notice, and logs in with username/password + MFA (see the
  CAPTCHA note below).
- **Garmin Connect [Personal API](https://developer.garmin.com/gc-developer-program/personal/personal-api/)**
  (official) — for individuals accessing their own data; not for
  commercial or multi-user apps (that's the separate B2B Developer
  Program / Health API). Mechanics, per Garmin's FAQ:
  - Create a key while logged in to Garmin Connect
    (Settings → [Personal API key](https://connect.garmin.com/app/settings/personalApiToken)).
    It's shown once; expiry is 30 / 90 / 180 days or 1 year, with an
    email reminder about a week before.
  - Exchange it for an access token at
    `POST https://personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token`
    (`Authorization: ApiKey <key>`). Tokens last 24h; no refresh tokens —
    just request a new one.
  - No password, MFA or CAPTCHA, and no rotating refresh token to
    persist.
  - Garmin's reference client,
    [garmin/connect-personal-api-python](https://github.com/garmin/connect-personal-api-python),
    is read-only (GET) and wraps: activities (search, details, workouts,
    file download), sleep, HRV, Body Battery, daily heart rate, HR zones,
    SpO2, fitness age, wellness activity summaries. Whether the API
    accepts writes (workout upload, calendar scheduling) and covers
    training readiness/status isn't confirmed yet — check the
    [Swagger docs](https://developer.garmin.com/gc-developer-program/personal/swagger-docs/).

**Direction:** `python-garminconnect` stays the source for now — it's
what's built and it's the only confirmed way to push workouts to the
calendar. We want to use the Personal API directly for the scenarios it
covers, starting with the read side of the daily sync (activities,
sleep, HRV, Body Battery, resting HR), which would remove the
token-rotation/CAPTCHA concerns for those calls. Calendar writes stay on
`python-garminconnect` unless the Swagger docs show write support.
Record the split as a new ADR (superseding/refining ADR 0002) once it's
decided.

(`python-garminconnect` was originally scoped around `garth` underneath it, per the upstream README at the time. `garth` is now deprecated — see [its maintainer's note](https://github.com/matin/garth/discussions/222) — and `python-garminconnect` (>=0.3) dropped it in favor of its own built-in token store. Functionally the same idea, simpler mechanics: see Phase 0 below.)

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
- Notify on flags however is convenient — a Telegram bot ping at the end of the sync is what's wired up (`garmin_sync/notify.py`).

### Storage note

The repo is **public**, so nothing sensitive goes into git:

- Activities, laps, wellness, signals, planned workouts, and the injury log live in an external Postgres database (Supabase free tier or similar), not committed.
- The Garmin session token lives only in the `GARMIN_TOKENS` GitHub Actions secret (auto-rotated by the workflow via a separate scoped PAT), never in git.
- The training plan itself (and its progress log/checkpoints) is the one thing deliberately committed and public — it's summary-level, not raw health data.
- Raw per-activity exports (`past_workouts/*.tcx`) stay local-only and gitignored — they carry GPS tracks and per-second HR.

See [README.md](../README.md) for the concrete setup and current implementation status.

## Open follow-ups

- Plan-adjuster module: act on the `signals` table's anomaly detections (currently detection-only, by design).
- Notifications on new signals: wired up via Telegram (`garmin_sync/notify.py`, called from `scripts/daily_sync.py`).
- Personal API: check the Swagger docs for write support and training
  readiness/status, then decide which calls move off
  `python-garminconnect` (new ADR). Key expiry (max 1 year) becomes a
  scheduled renewal, like the token re-bootstrap.
- Verify `garmin_sync/wellness.py`'s field mappings against a real account's data once the daily sync has run for a while; several of them are best-effort against Garmin's undocumented API.
