"""Fetch daily wellness data (sleep, HRV, resting HR, Body Battery, training
readiness/status) — the half of PLAN.md's problem 2 that Strava's activity
feed can't provide.

Garmin's wellness endpoints aren't publicly documented and several of these
response shapes (training status, body battery, stress) are only loosely
known from community reverse-engineering, not verified against a live
account here. Every extraction below is defensive (falls back to `None`
rather than raising) and the untouched raw response is always kept in
`raw` — treat the typed columns as convenience, not the source of truth,
until you've checked them against a real day's data.
"""

from __future__ import annotations

import logging
from typing import Any

from garminconnect import Garmin
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)


def _get(d: Any, *path: str, default: Any = None) -> Any:
    """Walk a chain of dict keys, returning `default` on any missing/wrong-typed step."""
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def fetch_wellness_day(garmin: Garmin, day: str) -> dict[str, Any]:
    """Pull every wellness signal for one YYYY-MM-DD day. Returns a dict with
    both the raw per-endpoint payloads (under "raw") and best-effort typed
    fields, ready for garmin_sync.db.upsert_wellness_day.
    """
    raw: dict[str, Any] = {}

    def _try(label: str, fn) -> Any:
        try:
            result = fn()
            raw[label] = result
            return result
        except Exception as e:
            logger.warning("Failed to fetch %s for %s: %s", label, day, e)
            raw[label] = None
            return None

    sleep = _try("sleep", lambda: garmin.get_sleep_data(day))
    hrv = _try("hrv", lambda: garmin.get_hrv_data(day))
    rhr_range = _try("rhr", lambda: garmin.get_rhr_daily(day, day))
    readiness = _try("training_readiness", lambda: garmin.get_training_readiness(day))
    training_status = _try("training_status", lambda: garmin.get_training_status(day))
    body_battery = _try("body_battery", lambda: garmin.get_body_battery(day, day))

    sleep_dto = _get(sleep, "dailySleepDTO", default={})
    resting_hr = None
    if isinstance(rhr_range, list) and rhr_range:
        resting_hr = rhr_range[0].get("value")

    training_readiness_score = None
    if isinstance(readiness, list) and readiness:
        training_readiness_score = readiness[0].get("score")

    training_status_value = None
    try:
        latest = _get(training_status, "mostRecentTrainingStatus", "latestTrainingStatusData", default={})
        if isinstance(latest, dict) and latest:
            first_device = next(iter(latest.values()))
            training_status_value = (first_device or {}).get("trainingStatus")
    except Exception as e:
        logger.warning("Failed to parse training_status for %s: %s", day, e)

    bb_high = bb_low = None
    if isinstance(body_battery, list) and body_battery:
        values_array = body_battery[0].get("bodyBatteryValuesArray") or []
        levels = [v[1] for v in values_array if isinstance(v, list) and len(v) > 1 and isinstance(v[1], (int, float))]
        if levels:
            bb_high, bb_low = max(levels), min(levels)

    return {
        "day": day,
        "sleep_score": _get(sleep_dto, "sleepScores", "overall", "value"),
        "sleep_duration_s": sleep_dto.get("sleepTimeSeconds") if isinstance(sleep_dto, dict) else None,
        "deep_sleep_s": sleep_dto.get("deepSleepSeconds") if isinstance(sleep_dto, dict) else None,
        "light_sleep_s": sleep_dto.get("lightSleepSeconds") if isinstance(sleep_dto, dict) else None,
        "rem_sleep_s": sleep_dto.get("remSleepSeconds") if isinstance(sleep_dto, dict) else None,
        "awake_s": sleep_dto.get("awakeSleepSeconds") if isinstance(sleep_dto, dict) else None,
        "resting_hr": resting_hr,
        "hrv_last_night_avg": _get(hrv, "hrvSummary", "lastNightAvg"),
        "hrv_status": _get(hrv, "hrvSummary", "status"),
        "body_battery_high": bb_high,
        "body_battery_low": bb_low,
        "stress_avg": None,  # not wired up yet — see get_stress_data if needed later
        "training_readiness": training_readiness_score,
        "training_status": training_status_value,
        "raw": Jsonb(raw),
    }
