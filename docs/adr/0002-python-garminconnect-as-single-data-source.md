# ADR 0002: python-garminconnect as the single Garmin data source

- **Status:** Accepted
- **Date:** 2026-08-27 (recorded retroactively 2026-11-06)
- **Deciders:** Dmitrijs Ozolins

## Context

The project needs two kinds of Garmin data: workouts/activities (for
analysis) and wellness — sleep, HRV, resting HR, Body Battery, training
readiness/status (for adjusting the plan after bad sleep, missed
sessions, etc.).

Garmin has no self-serve API for individuals. Its official API (Garmin
Connect Developer Program / Health API) is a B2B partner program behind a
formal agreement.

## Options considered

1. **Garmin Health API (official).** Partner-only; not obtainable for a
   personal project.
2. **Strava as a side door.** Garmin pushes activities to Strava as a
   partner; Strava's public OAuth API exposes them (~1000 req/day).
   Documented and stable, but carries activity data only — no sleep, HRV,
   Body Battery, stress or training readiness, which is exactly the
   plan-adjustment half.
3. **`python-garminconnect`.** Unofficial wrapper over Garmin Connect's
   web endpoints. Covers activities *and* wellness in one place, plus
   workout upload and calendar scheduling.

## Decision

**Option 3:** `python-garminconnect` is the single source for everything.

Originally scoped on top of `garth`; `garth` has since been deprecated and
`python-garminconnect` >= 0.3 ships its own token store, which is what's
used now (see `garmin_sync/auth.py`).

## Consequences

- One library, one auth flow, for both reading data and pushing workouts
  to the calendar (`scripts/push_week_runs.py`).
- The API is undocumented and can change without notice; response shapes
  vary by account/device. Mitigated by keeping the untouched response in a
  `raw` JSONB column next to best-effort typed columns (see
  [ADR 0003](0003-health-data-in-external-postgres.md)).
- Logins from datacenter IPs risk CAPTCHA/anti-bot blocks; handled by
  [ADR 0004](0004-token-only-garmin-session-in-automation.md).
- Historical backfill (Sep 2024 onward) was dropped from scope: that
  history was obtained once via manual TCX export into `past_workouts/`.
