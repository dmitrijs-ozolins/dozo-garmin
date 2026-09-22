#!/usr/bin/env python3
"""Phase 2 — daily automated sync (PLAN.md).

Runs in GitHub Actions on a schedule (see .github/workflows/daily-sync.yml)
or locally for testing. Each run: resumes the Garmin session from
GARMIN_TOKENS, fetches one day's activities + wellness data (sleep, HRV,
resting HR, Body Battery, training readiness/status), stores it in
Postgres, and runs the anomaly checks in garmin_sync/signals.py.

Usage:
    python scripts/daily_sync.py                        # yesterday (UTC)
    python scripts/daily_sync.py --date 2026-08-20
    python scripts/daily_sync.py --dump-tokens-to /tmp/t.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from garmin_sync.activities import fetch_activities, fetch_laps, to_activity_row, to_lap_row
from garmin_sync.auth import dump_tokens, login_from_env
from garmin_sync.db import connect, init_db, log_sync_run, upsert_activity, upsert_laps, upsert_wellness_day
from garmin_sync.signals import run_all_checks
from garmin_sync.wellness import fetch_wellness_day

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("daily_sync")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD; defaults to yesterday (UTC)")
    parser.add_argument(
        "--dump-tokens-to", default=None,
        help="Write the (possibly Garmin-rotated) session token JSON here, for the workflow to re-upload as the GARMIN_TOKENS secret",
    )
    args = parser.parse_args()

    load_dotenv()
    day = args.date or (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()

    init_db()
    garmin = login_from_env()
    logger.info("Logged in as %s. Syncing %s", garmin.full_name or garmin.display_name, day)

    activities = fetch_activities(garmin, day, day)
    wellness = fetch_wellness_day(garmin, day)

    with connect() as conn:
        for activity in activities:
            activity_id = activity.get("activityId")
            if activity_id is None:
                logger.warning("Skipping activity with no activityId: %r", activity.get("activityName"))
                continue
            upsert_activity(conn, to_activity_row(activity))
            laps = fetch_laps(garmin, activity_id)
            upsert_laps(conn, activity_id, [to_lap_row(lap, i) for i, lap in enumerate(laps)])

        upsert_wellness_day(conn, wellness)
        run_all_checks(conn, day)
        log_sync_run(conn, "daily", day, day, len(activities), "ok")
        conn.commit()

    logger.info("Synced %d activities + wellness for %s", len(activities), day)

    # Refresh happens transparently inside garmin.login()/connectapi() calls
    # above; the token this session ends with may differ from GARMIN_TOKENS.
    # Persisting it is what keeps the *next* CI run from resuming a stale
    # (possibly already-rotated) refresh token — see garmin_sync/auth.py.
    if args.dump_tokens_to:
        Path(args.dump_tokens_to).write_text(dump_tokens(garmin))
        logger.info("Wrote current session tokens to %s", args.dump_tokens_to)


if __name__ == "__main__":
    main()
