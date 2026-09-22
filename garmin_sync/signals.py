"""Anomaly signals for a future plan-adjuster (PLAN.md Phase 2).

This module only *detects* — missed session, low sleep score, resting-HR
spike, manual injury flag — and writes clean structured rows to the
`signals` table. Deciding how to adjust the training plan in response is a
separate, later module (per PLAN.md: keep "detect an anomaly" separate
from "decide how to adjust the plan").

Planned workouts and injury flags are read from the `planned_workouts` /
`injury_log` tables (managed via scripts/plan_cli.py) rather than the
YAML files PLAN.md originally sketched — this repo is public, so that
data lives in the external DB instead of git. See garmin_sync/db.py.
"""

from __future__ import annotations

import psycopg

from garmin_sync.db import insert_signal

# Thresholds — tune once you have real baseline data.
LOW_SLEEP_SCORE_THRESHOLD = 60
RHR_SPIKE_BPM_ABOVE_BASELINE = 7


def check_missed_workout(conn: psycopg.Connection, day: str) -> None:
    planned = conn.execute(
        "SELECT workout_type, description FROM planned_workouts WHERE day = %(day)s",
        {"day": day},
    ).fetchall()
    if not planned:
        return
    row = conn.execute(
        "SELECT count(*) AS n FROM activities WHERE start_time_local::date = %(day)s",
        {"day": day},
    ).fetchone()
    if row and row["n"] == 0:
        for session in planned:
            insert_signal(
                conn, day, "missed_workout", "warning",
                f"Planned {session['workout_type'] or 'workout'} "
                f"({session['description'] or ''}) not found in Garmin activities",
            )


def check_low_sleep(conn: psycopg.Connection, day: str, threshold: int = LOW_SLEEP_SCORE_THRESHOLD) -> None:
    row = conn.execute(
        "SELECT sleep_score FROM wellness_daily WHERE day = %(day)s",
        {"day": day},
    ).fetchone()
    if row and row["sleep_score"] is not None and row["sleep_score"] < threshold:
        insert_signal(conn, day, "low_sleep", "warning", f"Sleep score {row['sleep_score']} < {threshold}")


def check_rhr_spike(
    conn: psycopg.Connection,
    day: str,
    baseline_days: int = 28,
    spike_bpm: int = RHR_SPIKE_BPM_ABOVE_BASELINE,
) -> None:
    today_row = conn.execute(
        "SELECT resting_hr FROM wellness_daily WHERE day = %(day)s", {"day": day}
    ).fetchone()
    if not today_row or today_row["resting_hr"] is None:
        return
    baseline_row = conn.execute(
        """
        SELECT avg(resting_hr) AS avg_rhr FROM wellness_daily
        WHERE day < %(day)s AND day >= (%(day)s::date - %(window)s * interval '1 day')
          AND resting_hr IS NOT NULL
        """,
        {"day": day, "window": baseline_days},
    ).fetchone()
    baseline = baseline_row["avg_rhr"] if baseline_row else None
    if baseline is None:
        return
    delta = today_row["resting_hr"] - baseline
    if delta >= spike_bpm:
        insert_signal(
            conn, day, "rhr_spike", "warning",
            f"Resting HR {today_row['resting_hr']} is {delta:.1f} bpm above the "
            f"{baseline_days}-day baseline ({baseline:.1f})",
        )


def check_manual_injury_flags(conn: psycopg.Connection, day: str) -> None:
    """Re-raises a signal for every day an injury stays 'active' (until
    resolved via scripts/plan_cli.py resolve-injury), so a plan-adjuster
    reading "today's signals" always sees it.
    """
    rows = conn.execute(
        "SELECT severity, note FROM injury_log WHERE status = 'active' AND day <= %(day)s",
        {"day": day},
    ).fetchall()
    for row in rows:
        insert_signal(conn, day, "manual_injury", row["severity"] or "warning", row["note"] or "")


def run_all_checks(conn: psycopg.Connection, day: str) -> None:
    check_missed_workout(conn, day)
    check_low_sleep(conn, day)
    check_rhr_spike(conn, day)
    check_manual_injury_flags(conn, day)
