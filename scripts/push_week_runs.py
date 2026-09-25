#!/usr/bin/env python3
"""One-off: push this week's remaining running workouts to the Garmin
Connect calendar (training_plan/phases/phase_1_special_prep_1.md, Week 1).

Gym/pool days are intentionally left out — Garmin can't represent them
usefully as structured workouts, and the ask was running only.

Usage:
    python scripts/push_week_runs.py            # upload + schedule
    python scripts/push_week_runs.py --dry-run   # build and print, no API calls
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin_sync.auth import DEFAULT_TOKENSTORE
from garminconnect import Garmin
from garminconnect.workout import (
    ConditionType,
    ExecutableStep,
    RepeatGroup,
    RunningWorkout,
    StepType,
    TargetType,
    WorkoutSegment,
    create_repeat_group,
)

RUNNING_SPORT_TYPE = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}
NO_TARGET = {"workoutTargetTypeId": TargetType.NO_TARGET, "workoutTargetTypeKey": "no.target", "displayOrder": 1}


def hr_target(low_bpm: float, high_bpm: float) -> dict:
    return {
        "targetType": {
            "workoutTargetTypeId": TargetType.HEART_RATE_ZONE,
            "workoutTargetTypeKey": "heart.rate.zone",
            "displayOrder": 4,
        },
        "one": low_bpm,
        "two": high_bpm,
    }


def pace_target(low_kmh_pace_s: float, high_kmh_pace_s: float) -> dict:
    """low/high given as seconds-per-km; converts to Garmin's m/s speed bounds."""
    return {
        "targetType": {
            "workoutTargetTypeId": TargetType.PACE_ZONE,
            "workoutTargetTypeKey": "pace.zone",
            "displayOrder": 6,
        },
        # faster pace (fewer seconds/km) -> higher speed
        "one": 1000.0 / high_kmh_pace_s,
        "two": 1000.0 / low_kmh_pace_s,
    }


def distance_step(order: int, meters: float, step_type_id: int, step_type_key: str, target: dict | None = None) -> ExecutableStep:
    kwargs = dict(
        stepOrder=order,
        stepType={"stepTypeId": step_type_id, "stepTypeKey": step_type_key, "displayOrder": step_type_id},
        endCondition={
            "conditionTypeId": ConditionType.DISTANCE,
            "conditionTypeKey": "distance",
            "displayOrder": 3,
            "displayable": True,
        },
        endConditionValue=meters,
        targetType=target["targetType"] if target else NO_TARGET,
    )
    if target:
        kwargs["targetValueOne"] = target["one"]
        kwargs["targetValueTwo"] = target["two"]
    return ExecutableStep(**kwargs)


def build_friday() -> RunningWorkout:
    # Ф1 Нед1 Пт 25.09 — Run 8km @HR<=145 (phase_1_special_prep_1.md L47)
    step = distance_step(1, 8000, StepType.INTERVAL, "interval", hr_target(125, 145))
    return RunningWorkout(
        workoutName="Phase1: Recovery 8km",
        estimatedDurationInSecs=2520,
        description="Recovery run, HR <=145 (phase_1_special_prep_1.md)",
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[step])],
    )


def build_saturday() -> RunningWorkout:
    # Ф1 Нед1 Сб 26.09 — 4km w + 8x500m in 2:08 (p500m jog 2:30) + 2km c (phase_1_special_prep_1.md L48)
    warmup = distance_step(1, 4000, StepType.WARMUP, "warmup")
    work = distance_step(1, 500, StepType.INTERVAL, "interval", pace_target(4 * 60 + 12, 4 * 60 + 20))
    recovery = distance_step(2, 500, StepType.RECOVERY, "recovery")
    repeats = create_repeat_group(iterations=8, workout_steps=[work, recovery], step_order=2)
    cooldown = distance_step(3, 2000, StepType.COOLDOWN, "cooldown")
    return RunningWorkout(
        workoutName="Phase1: 8x500m intervals",
        estimatedDurationInSecs=4234,
        description="4km warmup + 8x500m @ ~4:16/km (500m jog recovery ~2:30) + 2km cooldown "
        "(phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


def build_sunday() -> RunningWorkout:
    # Ф1 Нед1 Вс 27.09 — Run 12km @HR145 (phase_1_special_prep_1.md L49)
    step = distance_step(1, 12000, StepType.INTERVAL, "interval", hr_target(140, 150))
    return RunningWorkout(
        workoutName="Phase1: Long run 12km",
        estimatedDurationInSecs=3780,
        description="Long run, HR ~145 (phase_1_special_prep_1.md)",
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[step])],
    )


WORKOUTS = [
    ("2026-09-25", build_friday),
    ("2026-09-26", build_saturday),
    ("2026-09-27", build_sunday),
]

# workout_id of each workout already uploaded+scheduled by a prior run of this
# script (with Russian names) -- used by --update to rename them in place
# without touching their calendar schedule.
ALREADY_PUSHED_IDS = {
    "2026-09-25": 1709031635,
    "2026-09-26": 1709031645,
    "2026-09-27": 1709031649,
}


def _login() -> Garmin:
    # Resume from the cached token only (scripts/bootstrap_auth.py already ran) --
    # no email/password prompt needed, mirrors garmin_sync.auth.login_from_env.
    def _no_mfa() -> str:
        raise RuntimeError("Cached session needs MFA again -- rerun scripts/bootstrap_auth.py")

    garmin = Garmin(prompt_mfa=_no_mfa)
    garmin.login(tokenstore=str(DEFAULT_TOKENSTORE))
    return garmin


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    update = "--update" in sys.argv

    if dry_run:
        for date_str, builder in WORKOUTS:
            workout = builder()
            print(f"=== {date_str}: {workout.workoutName} ===")
            print(workout.to_dict())
            print()
        return

    garmin = _login()

    if update:
        for date_str, builder in WORKOUTS:
            workout_id = ALREADY_PUSHED_IDS[date_str]
            workout = builder()
            garmin.update_workout(workout_id, workout.to_dict())
            print(f"UPDATED  {date_str}  {workout.workoutName}  (workout_id={workout_id})")
        return

    for date_str, builder in WORKOUTS:
        workout = builder()
        uploaded = garmin.upload_running_workout(workout)
        workout_id = uploaded.get("workoutId")
        if not workout_id:
            print(f"FAILED to upload {workout.workoutName}: {uploaded}")
            continue
        garmin.schedule_workout(workout_id, date_str)
        print(f"OK  {date_str}  {workout.workoutName}  (workout_id={workout_id})")


if __name__ == "__main__":
    main()
