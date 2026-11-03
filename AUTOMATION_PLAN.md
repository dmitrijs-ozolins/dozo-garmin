# Automated Garmin calendar updates (Mac mini)

Goal: the workout schedule lands on the Garmin Connect calendar
automatically, on a schedule, from a dedicated Mac mini — no manual
`push_week_runs.py --week N` runs.

## Where things stand (2026-11-03)

- **Calendar push is manual.** `scripts/push_week_runs.py` holds a
  hand-written builder function per workout (`build_p2w1_tuesday`, ...)
  and a `WEEKS` dict; it's run by hand with `--week N`. Every reschedule
  ("Tue missed → moved to Wed") means editing Python, and in-place fixes
  rely on hardcoded IDs (`ALREADY_PUSHED_IDS`, workout_id comments).
- **Daily data sync runs on GitHub Actions** (`.github/workflows/daily-sync.yml`),
  re-uploading the rotated Garmin token to the `GARMIN_TOKENS` secret via
  `GH_SECRETS_PAT` after each run.
- **The library already supports the missing pieces.** `garminconnect`
  0.3.11 has `get_scheduled_workouts`, `schedule_workout`,
  `unschedule_workout`, `update_workout`, `delete_workout`.

## Steps

### 1. Plan as data, not Python

- One file per week, e.g. `training_plan/weeks/p2w3.yaml`: date →
  workout name, sport, steps (warmup by time, repeats, km/h or pace
  targets, HR caps, incline).
- One generic builder turns a step spec into a `RunningWorkout` /
  `CyclingWorkout`, reusing the existing helpers in `push_week_runs.py`
  (`time_step`, `distance_step`, `hr_target`, `pace_target`,
  `power_target`, `lap_button_step`).
- Rescheduling = editing a date in YAML, no code changes.
- Start by converting the current and next week from `WEEKS` to YAML.
- Respect the existing workout-format conventions (treadmill intervals at
  1% in km/h with time steps, hills at 5% max 16 reps with time-based
  warmup, no treadmill pace comparison).

### 2. Idempotent calendar sync

- New `scripts/sync_calendar.py --horizon 14d`: compare the desired
  workouts (YAML) against what's scheduled on Garmin in that window.
  - missing → upload + schedule
  - content changed → `update_workout` in place
  - removed / moved → unschedule (and delete if it's one we created)
- Only ever touch workouts this tool created: tag them with a marker in
  the description, and keep a mapping table in Postgres
  (date → workout_id, schedule_id, content hash). This replaces
  `ALREADY_PUSHED_IDS`.
- Re-running must be a no-op — that's what makes scheduling it safe.
- Support `--dry-run` that prints the planned diff.

### 3. Mac mini runtime (launchd)

- Repo cloned on the mini, `.venv` + `pip install -r requirements.txt`,
  `.env` with `DATABASE_URL` (+ Telegram vars).
- Run `scripts/bootstrap_auth.py` on the mini once; token lives at
  `~/.dozo-garmin/garmin_tokens.json`. Residential IP → much less
  CAPTCHA risk than GitHub's datacenter runners.
- LaunchAgent plist in `~/Library/LaunchAgents/` using
  `StartCalendarInterval` (e.g. daily sync 07:00, calendar sync right
  after). Unlike cron, launchd runs a missed job when the machine wakes.
- Keep the plist(s) in the repo (e.g. `launchd/`) with an install
  script; log to `~/Library/Logs/dozo-garmin/`.
- Keep the box up: `sudo pmset -a sleep 0 autorestart 1`, plus
  auto-login so the LaunchAgent comes back after a power cut. With
  FileVault on, the Mac waits for a password after a reboot — accept
  that or disable FileVault on this machine.
- Failures → Telegram via `garmin_sync/notify.py`, so a token that needs
  re-bootstrapping gets noticed.

### 4. Move the daily sync off GitHub Actions

- Garmin rotates the refresh token. If GitHub Actions and the Mac mini
  both use the same Garmin login, whichever refreshes first breaks the
  other. One machine must own the token.
- Run `scripts/daily_sync.py` from launchd on the mini, reading the local
  token file (add a token-file path to `login_from_env` / or use
  `DEFAULT_TOKENSTORE`).
- Remove the `schedule:` trigger from `daily-sync.yml` (optionally keep
  `workflow_dispatch`), drop the token re-upload step, and retire the
  `GH_SECRETS_PAT` / `GARMIN_TOKENS` secrets.
- Update README.md "One-time setup" / "Phase 1" to describe the Mac mini
  setup instead of GitHub Actions.

### 5. (Optional) Auto-adjusting plan via Claude

- Weekly (or on a missed-workout signal), launchd runs `claude -p` on the
  mini: reads the phase plan (`training_plan/phases/`), last week's
  activities + `signals` from Postgres, and the workout-format rules;
  writes next week's YAML.
- Step 2 then pushes it; Telegram sends a summary so changes can be
  vetoed before the week starts.
- This is the "plan-adjuster" from PLAN.md's open follow-ups. Keep it
  separate from detection (signals), as PLAN.md requires.

## Order

1 → 2 → verify manually (`--dry-run`, then a real run) → 3 + 4 →
run stable for a couple of weeks → 5 if wanted.

## Open decision

What "automatic" means:

- **(a)** Weeks are still written by hand (Dima or Claude in a session)
  as YAML; the mini only keeps the Garmin calendar in sync with it.
- **(b)** The mini also generates/adjusts weeks itself via `claude -p`.

Recommendation: start with (a); (b) builds on it.
