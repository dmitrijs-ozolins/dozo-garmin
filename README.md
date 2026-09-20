# dozo-garmin

Garmin Connect data sync — historical backfill + daily automated pull, for
workout-structure analysis and training-plan adjustment. Design rationale
lives in [PLAN.md](PLAN.md); this file is the "how to actually run it" doc.

**This repo is public.** No health data, session tokens, or personal
training-plan/injury details are ever committed to it — they live in an
external Postgres database and in GitHub Actions secrets. See "Where data
lives" below before you add anything to this repo.

## Where data lives

| What | Where | Why |
|---|---|---|
| Activities, laps, wellness, signals, planned workouts, injury log | Postgres (Supabase free tier or similar), via `DATABASE_URL` | Health/personal data — never in git, since the repo is public |
| Garmin session token | `GARMIN_TOKENS` GitHub Actions secret, auto-rotated by the workflow via a PAT | Grants account access — never in git either |
| Code, schema, workflow | This repo | Nothing sensitive |

## One-time setup

1. **Create a Postgres database.** Easiest: a free [Supabase](https://supabase.com)
   project. Grab its connection string (Project Settings → Database →
   Connection string → URI). Use the "Session pooler" URI (port 6543) for
   CI; either works for local use.

2. **Install dependencies:**

   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # fill in DATABASE_URL
   ```

3. **Phase 0 — bootstrap Garmin auth (local, interactive, one-time):**

   ```bash
   python scripts/bootstrap_auth.py
   ```

   Prompts for your Garmin email/password (or reads `GARMIN_EMAIL` /
   `GARMIN_PASSWORD` from the environment) and an MFA code if you have MFA
   enabled, then writes a small session-token file to
   `~/.dozo-garmin/garmin_tokens.json` — deliberately outside the repo.
   The script prints the exact next steps; the short version:

4. **Set GitHub Actions secrets** (repo Settings → Secrets and variables →
   Actions):

   - `DATABASE_URL` — the Postgres connection string from step 1.
   - `GARMIN_TOKENS` — contents of `~/.dozo-garmin/garmin_tokens.json` from
     step 3 (`gh secret set GARMIN_TOKENS < ~/.dozo-garmin/garmin_tokens.json`,
     or paste it into the UI).
   - `GH_SECRETS_PAT` — a fine-grained [Personal Access Token](https://github.com/settings/tokens?type=beta)
     scoped to *only this repo*, with **Secrets: write** permission (repo
     secrets, not Actions itself). The daily workflow uses it to rewrite
     `GARMIN_TOKENS` whenever Garmin rotates the refresh token — without
     this, the cached session eventually goes stale and the workflow starts
     failing (see `garmin_sync/auth.py`).

   Expect to redo step 3 roughly once a year, or whenever Garmin revokes
   the token — treat it as scheduled manual maintenance, not something CI
   auto-recovers from (see PLAN.md).

## Phase 1 — historical backfill (local, one-time)

```bash
python scripts/backfill.py --start 2024-09-01 --end 2025-12-31
```

Pulls every activity in the range plus its lap/split structure into
Postgres (`activities` + `laps` tables) — the dataset for the
workout-structure analysis. Doesn't touch wellness data (see the script's
docstring for why). Add `--fit-dir data/fit` to also save each activity's
original FIT file locally (gitignored) if the analysis needs
second-by-second data beyond laps.

## Phase 2 — daily sync (GitHub Actions)

`.github/workflows/daily-sync.yml` runs `scripts/daily_sync.py` once a day
(08:00 UTC) plus on manual `workflow_dispatch`. Each run fetches the
previous day's activities and wellness (sleep, HRV, resting HR, Body
Battery, training readiness/status), stores it, and runs the anomaly
checks in `garmin_sync/signals.py` (missed workout, low sleep, resting-HR
spike, active injury flag) into the `signals` table.

Run it locally the same way:

```bash
python scripts/daily_sync.py --date 2026-08-20
```

(needs `GARMIN_TOKENS` and `DATABASE_URL` in your `.env`.)

### Planned workouts & injury log

Managed via `scripts/plan_cli.py` (writes to Postgres, not files):

```bash
python scripts/plan_cli.py add-workout 2026-09-01 running "Easy 8km"
python scripts/plan_cli.py add-injury 2026-08-20 "Left knee soreness" --severity warning
python scripts/plan_cli.py resolve-injury 3
python scripts/plan_cli.py list-workouts
python scripts/plan_cli.py list-injuries --active-only
```

## What's not built yet

- **Plan-adjuster**: `signals` rows are structured anomaly *detections*
  only (PLAN.md deliberately keeps "detect" separate from "decide"). Acting
  on them — actually adjusting the training plan — is a separate module.
- **Notifications**: nothing pings you on a new signal yet. Cheapest next
  step is probably a Slack/Pushover call at the end of `daily_sync.py`
  when `run_all_checks` finds something.
- **Field-mapping verification**: `garmin_sync/wellness.py`'s typed columns
  (sleep score, HRV, training status, Body Battery high/low, ...) are
  best-effort against Garmin's undocumented API, not verified against a
  real account in this environment. Every row also keeps the untouched API
  response in a `raw` JSONB column — check a real day's `raw` against the
  typed columns after your first sync and adjust `wellness.py` if anything
  looks off.
- **Workout-structure analysis itself** — out of scope here per PLAN.md;
  this repo only gets the data into Postgres.
