"""Fetch activities + lap/split structure from Garmin Connect.

Field mappings below (`_extract_activity`, `_extract_lap`) are best-effort:
Garmin's activity API isn't publicly documented, so these follow the field
names this library's community has used for years (activityId,
startTimeLocal, lapDTOs, ...). Every row also stores the full raw response
in `raw` — if a typed column ever looks wrong, `raw` is the fallback, not a
second data pull.
"""

from __future__ import annotations

import logging
from typing import Any

from garminconnect import Garmin
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)


def fetch_activities(garmin: Garmin, start: str, end: str) -> list[dict[str, Any]]:
    """Raw activity summaries for [start, end], both YYYY-MM-DD, inclusive."""
    return garmin.get_activities_by_date(start, end, sortorder="asc")


def fetch_laps(garmin: Garmin, activity_id: int) -> list[dict[str, Any]]:
    """Raw lap/split dicts for one activity, oldest first."""
    splits = garmin.get_activity_splits(str(activity_id))
    return splits.get("lapDTOs", []) if splits else []


def to_activity_row(activity: dict[str, Any]) -> dict[str, Any]:
    """Map a raw activity summary dict onto the `activities` table shape."""
    activity_type = activity.get("activityType") or {}
    return {
        "activity_id": activity.get("activityId"),
        "start_time_local": activity.get("startTimeLocal"),
        "activity_type": activity_type.get("typeKey"),
        "name": activity.get("activityName"),
        "duration_s": activity.get("duration"),
        "distance_m": activity.get("distance"),
        "calories": activity.get("calories"),
        "avg_hr": activity.get("averageHR"),
        "max_hr": activity.get("maxHR"),
        "avg_speed_mps": activity.get("averageSpeed"),
        "elevation_gain_m": activity.get("elevationGain"),
        "training_effect_aerobic": activity.get("aerobicTrainingEffect"),
        "training_effect_anaerobic": activity.get("anaerobicTrainingEffect"),
        "raw": Jsonb(activity),
    }


def to_lap_row(lap: dict[str, Any], lap_index: int) -> dict[str, Any]:
    """Map a raw lap/split dict onto the `laps` table shape."""
    return {
        "lap_index": lap.get("lapIndex", lap_index),
        "start_time_local": lap.get("startTimeLocal") or lap.get("startTimeGMT"),
        "duration_s": lap.get("duration"),
        "distance_m": lap.get("distance"),
        "avg_hr": lap.get("averageHR"),
        "max_hr": lap.get("maxHR"),
        "avg_speed_mps": lap.get("averageSpeed"),
        "raw": Jsonb(lap),
    }
