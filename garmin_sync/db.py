"""Postgres storage for Garmin data.

The repo is public, so — unlike PLAN.md's original "commit SQLite to git"
sketch — health data is never written to the repo. It lives in an external
Postgres database (Supabase free tier or similar), reached via the
DATABASE_URL env var. Schema mirrors what PLAN.md calls for: one table for
activities, one for lap splits, one for daily wellness, plus small
bookkeeping tables for the anomaly signals and sync run history.

Every table also keeps a `raw` JSONB column with the untouched API
response. Garmin's endpoints aren't publicly documented and shapes vary by
account/device, so the typed columns below are a best-effort extraction
(see garmin_sync/activities.py and garmin_sync/wellness.py) — `raw` is the
source of truth if a typed column ever looks wrong.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    activity_id BIGINT PRIMARY KEY,
    start_time_local TIMESTAMPTZ NOT NULL,
    activity_type TEXT,
    name TEXT,
    duration_s DOUBLE PRECISION,
    distance_m DOUBLE PRECISION,
    calories DOUBLE PRECISION,
    avg_hr INTEGER,
    max_hr INTEGER,
    avg_speed_mps DOUBLE PRECISION,
    elevation_gain_m DOUBLE PRECISION,
    training_effect_aerobic DOUBLE PRECISION,
    training_effect_anaerobic DOUBLE PRECISION,
    raw JSONB,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS laps (
    activity_id BIGINT NOT NULL REFERENCES activities(activity_id) ON DELETE CASCADE,
    lap_index INTEGER NOT NULL,
    start_time_local TIMESTAMPTZ,
    duration_s DOUBLE PRECISION,
    distance_m DOUBLE PRECISION,
    avg_hr INTEGER,
    max_hr INTEGER,
    avg_speed_mps DOUBLE PRECISION,
    raw JSONB,
    PRIMARY KEY (activity_id, lap_index)
);

CREATE TABLE IF NOT EXISTS wellness_daily (
    day DATE PRIMARY KEY,
    sleep_score INTEGER,
    sleep_duration_s DOUBLE PRECISION,
    deep_sleep_s DOUBLE PRECISION,
    light_sleep_s DOUBLE PRECISION,
    rem_sleep_s DOUBLE PRECISION,
    awake_s DOUBLE PRECISION,
    resting_hr INTEGER,
    hrv_last_night_avg DOUBLE PRECISION,
    hrv_status TEXT,
    body_battery_high INTEGER,
    body_battery_low INTEGER,
    stress_avg INTEGER,
    training_readiness INTEGER,
    training_status TEXT,
    raw JSONB,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    day DATE NOT NULL,
    signal_type TEXT NOT NULL,  -- missed_workout | low_sleep | rhr_spike | manual_injury
    severity TEXT,
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Planned workouts and injury flags. PLAN.md originally sketched these as
-- YAML files in the repo, but this repo is public — personal training-plan
-- and injury details stay out of git entirely and live here instead. Manage
-- them with scripts/plan_cli.py.
CREATE TABLE IF NOT EXISTS planned_workouts (
    id BIGSERIAL PRIMARY KEY,
    day DATE NOT NULL,
    workout_type TEXT,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS injury_log (
    id BIGSERIAL PRIMARY KEY,
    day DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',  -- active | resolved
    severity TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sync_log (
    id BIGSERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind TEXT NOT NULL,  -- e.g. 'daily'
    range_start DATE,
    range_end DATE,
    activities_fetched INTEGER,
    status TEXT,
    detail TEXT
);
"""


def get_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env locally, or "
            "set the DATABASE_URL secret in GitHub Actions. See README.md."
        )
    return dsn


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        yield conn


def init_db() -> None:
    """Create tables if they don't exist yet. Safe to call on every run."""
    with connect() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def upsert_activity(conn: psycopg.Connection, activity: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO activities (
            activity_id, start_time_local, activity_type, name, duration_s,
            distance_m, calories, avg_hr, max_hr, avg_speed_mps,
            elevation_gain_m, training_effect_aerobic,
            training_effect_anaerobic, raw, fetched_at
        ) VALUES (
            %(activity_id)s, %(start_time_local)s, %(activity_type)s, %(name)s,
            %(duration_s)s, %(distance_m)s, %(calories)s, %(avg_hr)s,
            %(max_hr)s, %(avg_speed_mps)s, %(elevation_gain_m)s,
            %(training_effect_aerobic)s, %(training_effect_anaerobic)s,
            %(raw)s, now()
        )
        ON CONFLICT (activity_id) DO UPDATE SET
            start_time_local = EXCLUDED.start_time_local,
            activity_type = EXCLUDED.activity_type,
            name = EXCLUDED.name,
            duration_s = EXCLUDED.duration_s,
            distance_m = EXCLUDED.distance_m,
            calories = EXCLUDED.calories,
            avg_hr = EXCLUDED.avg_hr,
            max_hr = EXCLUDED.max_hr,
            avg_speed_mps = EXCLUDED.avg_speed_mps,
            elevation_gain_m = EXCLUDED.elevation_gain_m,
            training_effect_aerobic = EXCLUDED.training_effect_aerobic,
            training_effect_anaerobic = EXCLUDED.training_effect_anaerobic,
            raw = EXCLUDED.raw,
            fetched_at = now()
        """,
        activity,
    )


def upsert_laps(conn: psycopg.Connection, activity_id: int, laps: list[dict[str, Any]]) -> None:
    for lap in laps:
        lap = {**lap, "activity_id": activity_id}
        conn.execute(
            """
            INSERT INTO laps (
                activity_id, lap_index, start_time_local, duration_s,
                distance_m, avg_hr, max_hr, avg_speed_mps, raw
            ) VALUES (
                %(activity_id)s, %(lap_index)s, %(start_time_local)s,
                %(duration_s)s, %(distance_m)s, %(avg_hr)s, %(max_hr)s,
                %(avg_speed_mps)s, %(raw)s
            )
            ON CONFLICT (activity_id, lap_index) DO UPDATE SET
                start_time_local = EXCLUDED.start_time_local,
                duration_s = EXCLUDED.duration_s,
                distance_m = EXCLUDED.distance_m,
                avg_hr = EXCLUDED.avg_hr,
                max_hr = EXCLUDED.max_hr,
                avg_speed_mps = EXCLUDED.avg_speed_mps,
                raw = EXCLUDED.raw
            """,
            lap,
        )


def upsert_wellness_day(conn: psycopg.Connection, day_data: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO wellness_daily (
            day, sleep_score, sleep_duration_s, deep_sleep_s, light_sleep_s,
            rem_sleep_s, awake_s, resting_hr, hrv_last_night_avg, hrv_status,
            body_battery_high, body_battery_low, stress_avg,
            training_readiness, training_status, raw, fetched_at
        ) VALUES (
            %(day)s, %(sleep_score)s, %(sleep_duration_s)s, %(deep_sleep_s)s,
            %(light_sleep_s)s, %(rem_sleep_s)s, %(awake_s)s, %(resting_hr)s,
            %(hrv_last_night_avg)s, %(hrv_status)s, %(body_battery_high)s,
            %(body_battery_low)s, %(stress_avg)s, %(training_readiness)s,
            %(training_status)s, %(raw)s, now()
        )
        ON CONFLICT (day) DO UPDATE SET
            sleep_score = EXCLUDED.sleep_score,
            sleep_duration_s = EXCLUDED.sleep_duration_s,
            deep_sleep_s = EXCLUDED.deep_sleep_s,
            light_sleep_s = EXCLUDED.light_sleep_s,
            rem_sleep_s = EXCLUDED.rem_sleep_s,
            awake_s = EXCLUDED.awake_s,
            resting_hr = EXCLUDED.resting_hr,
            hrv_last_night_avg = EXCLUDED.hrv_last_night_avg,
            hrv_status = EXCLUDED.hrv_status,
            body_battery_high = EXCLUDED.body_battery_high,
            body_battery_low = EXCLUDED.body_battery_low,
            stress_avg = EXCLUDED.stress_avg,
            training_readiness = EXCLUDED.training_readiness,
            training_status = EXCLUDED.training_status,
            raw = EXCLUDED.raw,
            fetched_at = now()
        """,
        day_data,
    )


def insert_signal(conn: psycopg.Connection, day: str, signal_type: str, severity: str, detail: str) -> None:
    conn.execute(
        """
        INSERT INTO signals (day, signal_type, severity, detail)
        VALUES (%(day)s, %(signal_type)s, %(severity)s, %(detail)s)
        """,
        {"day": day, "signal_type": signal_type, "severity": severity, "detail": detail},
    )


def log_sync_run(
    conn: psycopg.Connection,
    kind: str,
    range_start: str | None,
    range_end: str | None,
    activities_fetched: int,
    status: str,
    detail: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO sync_log (kind, range_start, range_end, activities_fetched, status, detail)
        VALUES (%(kind)s, %(range_start)s, %(range_end)s, %(activities_fetched)s, %(status)s, %(detail)s)
        """,
        {
            "kind": kind,
            "range_start": range_start,
            "range_end": range_end,
            "activities_fetched": activities_fetched,
            "status": status,
            "detail": detail,
        },
    )
