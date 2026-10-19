#!/usr/bin/env python3
"""Push a week's running workouts to the Garmin Connect calendar
(training_plan/phases/phase_1_special_prep_1.md).

Gym/pool days are intentionally left out — Garmin can't represent them
usefully as structured workouts, and the ask was running only.

Usage:
    python scripts/push_week_runs.py --week 2            # upload + schedule
    python scripts/push_week_runs.py --week 2 --dry-run  # build and print, no API calls
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin_sync.auth import DEFAULT_TOKENSTORE
from garminconnect import Garmin
from garminconnect.workout import (
    ConditionType,
    CyclingWorkout,
    ExecutableStep,
    RepeatGroup,
    RunningWorkout,
    StepType,
    TargetType,
    WorkoutSegment,
    create_repeat_group,
)

RUNNING_SPORT_TYPE = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}
CYCLING_SPORT_TYPE = {"sportTypeId": 2, "sportTypeKey": "cycling", "displayOrder": 2}
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


def power_target(low_w: float, high_w: float) -> dict:
    return {
        "targetType": {
            "workoutTargetTypeId": TargetType.POWER_ZONE,
            "workoutTargetTypeKey": "power.zone",
            "displayOrder": 2,
        },
        "one": low_w,
        "two": high_w,
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


def time_step(order: int, seconds: float, step_type_id: int, step_type_key: str, target: dict | None = None) -> ExecutableStep:
    kwargs = dict(
        stepOrder=order,
        stepType={"stepTypeId": step_type_id, "stepTypeKey": step_type_key, "displayOrder": step_type_id},
        endCondition={
            "conditionTypeId": ConditionType.TIME,
            "conditionTypeKey": "time",
            "displayOrder": 2,
            "displayable": True,
        },
        endConditionValue=seconds,
        targetType=target["targetType"] if target else NO_TARGET,
    )
    if target:
        kwargs["targetValueOne"] = target["one"]
        kwargs["targetValueTwo"] = target["two"]
    return ExecutableStep(**kwargs)


def lap_button_step(order: int, step_type_id: int, step_type_key: str) -> ExecutableStep:
    return ExecutableStep(
        stepOrder=order,
        stepType={"stepTypeId": step_type_id, "stepTypeKey": step_type_key, "displayOrder": step_type_id},
        endCondition={
            "conditionTypeId": ConditionType.LAP_BUTTON,
            "conditionTypeKey": "lap.button",
            "displayOrder": 1,
            "displayable": True,
        },
        targetType=NO_TARGET,
    )


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


def build_w2_tuesday() -> RunningWorkout:
    # Ф1 Нед2 Вт 29.09 — Run 10km @HR145-160
    step = distance_step(1, 10000, StepType.INTERVAL, "interval", hr_target(145, 160))
    return RunningWorkout(
        workoutName="Phase1: Base 10km",
        estimatedDurationInSecs=2880,
        description="Base run, HR 145-160, aim 150-155 (phase_1_special_prep_1.md)",
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[step])],
    )


def build_w2_thursday() -> RunningWorkout:
    # Ф1 Нед2 Ср 30.09 (moved from Чт 01.10: 10k race Sat) — 4km w + 10x200m uphill 5-7% (p: walk down + 2' jog) + 2km c
    warmup = distance_step(1, 4000, StepType.WARMUP, "warmup")
    # No HR target on the rep: 200m is too short for HR to catch up; press lap after recovery.
    work = distance_step(1, 200, StepType.INTERVAL, "interval")
    recovery = lap_button_step(2, StepType.RECOVERY, "recovery")
    repeats = create_repeat_group(iterations=10, workout_steps=[work, recovery], step_order=2)
    cooldown = distance_step(3, 2000, StepType.COOLDOWN, "cooldown")
    return RunningWorkout(
        workoutName="Phase1: 10x200m hills",
        estimatedDurationInSecs=4500,
        description="4km warmup + 10x200m uphill 5-7%, RPE 8-9, HR 169-179 (>179 ease off). "
        "Recovery: walk down + 2' jog, press LAP to start next rep. 2km cooldown + stretch "
        "(phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


def build_w2_friday() -> RunningWorkout:
    # Ф1 Нед2 Пт 02.10 — pre-race: 5km easy + 4x100m strides
    easy = distance_step(1, 5000, StepType.INTERVAL, "interval", hr_target(120, 140))
    stride = distance_step(1, 100, StepType.INTERVAL, "interval")
    jog = distance_step(2, 150, StepType.RECOVERY, "recovery")
    strides = create_repeat_group(iterations=4, workout_steps=[stride, jog], step_order=2)
    return RunningWorkout(
        workoutName="Phase1: Easy 6km + strides",
        estimatedDurationInSecs=2100,
        description="Pre-race: 5km easy HR<=140 + 4x100m strides (fast & relaxed, ~3:20-3:30/km) "
        "with 150m easy jog (phase_1_special_prep_1.md)",
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[easy, strides])],
    )


def build_w2_saturday() -> RunningWorkout:
    # Ф1 Нед2 Сб 03.10 — 4km w + 10x500m in 2:07 (p500m jog 2:30) + 2km c
    warmup = distance_step(1, 4000, StepType.WARMUP, "warmup")
    work = distance_step(1, 500, StepType.INTERVAL, "interval", pace_target(4 * 60 + 10, 4 * 60 + 18))
    recovery = distance_step(2, 500, StepType.RECOVERY, "recovery")
    repeats = create_repeat_group(iterations=10, workout_steps=[work, recovery], step_order=2)
    cooldown = distance_step(3, 2000, StepType.COOLDOWN, "cooldown")
    return RunningWorkout(
        workoutName="Phase1: 10x500m intervals",
        estimatedDurationInSecs=5000,
        description="4km warmup + 10x500m in 2:07 (~4:14/km; 2:08-2:10 ok, HR cap ~172) "
        "(500m jog recovery ~2:30) + 2km cooldown + stretch (phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


def build_w2_sunday() -> RunningWorkout:
    # Ф1 Нед2 Вс 04.10 — day after 10k race: 11km very easy @HR<=140 (was 14km @HR145)
    step = distance_step(1, 11000, StepType.INTERVAL, "interval", hr_target(120, 140))
    return RunningWorkout(
        workoutName="Phase1: Recovery 11km",
        estimatedDurationInSecs=3800,
        description="Day after 10k race: very easy, HR <=140 (phase_1_special_prep_1.md)",
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[step])],
    )


def build_w3_tuesday() -> RunningWorkout:
    # Ф1 Нед3 Вт 06.10 — Run 12km @HR145-160
    step = distance_step(1, 12000, StepType.INTERVAL, "interval", hr_target(145, 160))
    return RunningWorkout(
        workoutName="Phase1: Base 12km",
        estimatedDurationInSecs=3480,
        description="Base run, HR 145-160 (phase_1_special_prep_1.md)",
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[step])],
    )


def build_w3_thursday() -> RunningWorkout:
    # Ф1 Нед3 Чт 08.10 — treadmill 5%: 20' w @HR<=140 + 16x200m @19 km/h (~38s), HR<=179 (p: 2' easy) + 10' c
    # Time-based steps: treadmill distance on the watch is unreliable, and the
    # warm-up is by time/HR, not distance.
    warmup = time_step(1, 20 * 60, StepType.WARMUP, "warmup", hr_target(120, 140))
    work = time_step(1, 38, StepType.INTERVAL, "interval")
    recovery = time_step(2, 120, StepType.RECOVERY, "recovery")
    repeats = create_repeat_group(iterations=16, workout_steps=[work, recovery], step_order=2)
    cooldown = time_step(3, 10 * 60, StepType.COOLDOWN, "cooldown")
    return RunningWorkout(
        workoutName="Phase1: 16x200m hills (treadmill)",
        estimatedDurationInSecs=20 * 60 + 16 * (38 + 120) + 10 * 60,
        description="Treadmill 5%: 20' warmup HR<=140 + 16x200m @19 km/h (~38s), HR<=179 "
        "(>179 ease off) with 2' easy + 10' cooldown + stretch (phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


def build_w3_friday() -> RunningWorkout:
    # Ф1 Нед3 Пт 09.10 — Run 8km @HR<=145
    step = distance_step(1, 8000, StepType.INTERVAL, "interval", hr_target(125, 145))
    return RunningWorkout(
        workoutName="Phase1: Recovery 8km",
        estimatedDurationInSecs=2520,
        description="Recovery run, HR <=145 (phase_1_special_prep_1.md)",
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[step])],
    )


def build_w3_saturday() -> RunningWorkout:
    # Ф1 Нед3 Сб 10.10 — 4km w + 10x600m in 2:34 (p500m jog 2:30) + 2km c
    warmup = distance_step(1, 4000, StepType.WARMUP, "warmup")
    work = distance_step(1, 600, StepType.INTERVAL, "interval", pace_target(4 * 60 + 13, 4 * 60 + 21))
    recovery = distance_step(2, 500, StepType.RECOVERY, "recovery")
    repeats = create_repeat_group(iterations=10, workout_steps=[work, recovery], step_order=2)
    cooldown = distance_step(3, 2000, StepType.COOLDOWN, "cooldown")
    return RunningWorkout(
        workoutName="Phase1: 10x600m intervals",
        estimatedDurationInSecs=5400,
        description="4km warmup + 10x600m in 2:34 (~4:17/km) (500m jog recovery ~2:30) "
        "+ 2km cooldown + stretch (phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


def build_w3_sunday() -> RunningWorkout:
    # Ф1 Нед3 Вс 11.10 — Run 14km @HR145
    step = distance_step(1, 14000, StepType.INTERVAL, "interval", hr_target(140, 150))
    return RunningWorkout(
        workoutName="Phase1: Long run 14km",
        estimatedDurationInSecs=4400,
        description="Long run, HR ~145 (phase_1_special_prep_1.md)",
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[step])],
    )


def build_w4_tuesday() -> RunningWorkout:
    # Ф1 Нед4 Вт 13.10 — Run 14km @HR145-160
    step = distance_step(1, 14000, StepType.INTERVAL, "interval", hr_target(145, 160))
    return RunningWorkout(
        workoutName="Phase1: Base 14km",
        estimatedDurationInSecs=3850,
        description="Base run, HR 145-160 (phase_1_special_prep_1.md)",
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[step])],
    )


def build_w4_thursday() -> RunningWorkout:
    # Ф1 Нед4 Чт 15.10 — treadmill 5%: 20' w @HR<=140 + 14x200m @19.5 km/h (~37s), HR<=179 (p: 2' easy) + 10' c
    warmup = time_step(1, 20 * 60, StepType.WARMUP, "warmup", hr_target(120, 140))
    work = time_step(1, 37, StepType.INTERVAL, "interval")
    recovery = time_step(2, 120, StepType.RECOVERY, "recovery")
    repeats = create_repeat_group(iterations=14, workout_steps=[work, recovery], step_order=2)
    cooldown = time_step(3, 10 * 60, StepType.COOLDOWN, "cooldown")
    return RunningWorkout(
        workoutName="Phase1: 14x200m hills @19.5 (treadmill)",
        estimatedDurationInSecs=20 * 60 + 14 * (37 + 120) + 10 * 60,
        description="Treadmill 5%: 20' warmup HR<=140 + 14x200m @19.5 km/h (~37s), HR<=179 "
        "(>179 ease off) with 2' easy + 10' cooldown + stretch (phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


def build_w4_saturday() -> RunningWorkout:
    # Ф1 Нед4 Сб 17.10 — 4km w + 12x600m in 2:32 (p500m jog 2:30) + 2km c
    warmup = distance_step(1, 4000, StepType.WARMUP, "warmup")
    work = distance_step(1, 600, StepType.INTERVAL, "interval", pace_target(4 * 60 + 9, 4 * 60 + 17))
    # Jog capped at 5:00/km: on 10.10 jogs drifted to 4:41-4:56 and HR never dropped below ~150.
    recovery = distance_step(2, 500, StepType.RECOVERY, "recovery", pace_target(5 * 60, 5 * 60 + 15))
    repeats = create_repeat_group(iterations=12, workout_steps=[work, recovery], step_order=2)
    cooldown = distance_step(3, 2000, StepType.COOLDOWN, "cooldown")
    return RunningWorkout(
        workoutName="Phase1: 12x600m intervals",
        estimatedDurationInSecs=5500,
        description="4km warmup + 12x600m in 2:32 (~4:13/km), even splits, first rep 2:33-2:34 "
        "(500m jog 2:30-2:38 = 5:00-5:15/km, not faster) "
        "+ 2km cooldown + stretch (phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


def build_w4_saturday_bike() -> CyclingWorkout:
    # Ф1 Нед4 Сб 17.10 — SWAP (can't run outside): trainer 8x3' @205-215W instead of 12x600m.
    # Power + RPE, not HR: on the bike legs are the limiter (26.09: 8x3' @212-227W felt hard).
    warmup = time_step(1, 15 * 60, StepType.WARMUP, "warmup", power_target(120, 160))
    work = time_step(1, 3 * 60, StepType.INTERVAL, "interval", power_target(205, 215))
    recovery = time_step(2, 90, StepType.RECOVERY, "recovery", power_target(110, 130))
    repeats = create_repeat_group(iterations=8, workout_steps=[work, recovery], step_order=2)
    cooldown = time_step(3, 10 * 60, StepType.COOLDOWN, "cooldown", power_target(110, 130))
    return CyclingWorkout(
        workoutName="Phase1: Bike 8x3' @205-215W",
        estimatedDurationInSecs=15 * 60 + 8 * (3 * 60 + 90) + 10 * 60,
        description="Trainer, replaces 12x600m. 15' warmup 120->160W + 3x20s spin-ups; "
        "8x3' @205-215W, cadence 90+, RPE 7-8 (last 2 up to 215-220W if good, drop to 200W "
        "rather than cut reps) / 1:30 easy ~120W; 10' cooldown. Optional +15-20' easy ~140W. "
        "Ignore HR (phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=CYCLING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


def build_w5_thursday() -> RunningWorkout:
    # Ф1 Нед5 Чт 22.10 — recovery week: treadmill 5%, 20' w + 10x200m @19.5 km/h (~37s) (p: 2' easy) + 10' c
    # Keep the new speed from 15.10, cut reps (was 10x @19 in the original plan).
    warmup = time_step(1, 20 * 60, StepType.WARMUP, "warmup", hr_target(120, 140))
    work = time_step(1, 37, StepType.INTERVAL, "interval")
    recovery = time_step(2, 120, StepType.RECOVERY, "recovery")
    repeats = create_repeat_group(iterations=10, workout_steps=[work, recovery], step_order=2)
    cooldown = time_step(3, 10 * 60, StepType.COOLDOWN, "cooldown")
    return RunningWorkout(
        workoutName="Phase1: 10x200m hills @19.5 (treadmill)",
        estimatedDurationInSecs=20 * 60 + 10 * (37 + 120) + 10 * 60,
        description="Recovery week. Treadmill 5%: 20' warmup HR<=140 + 10x200m @19.5 km/h (~37s), "
        "HR<=179 with 2' easy + 10' cooldown + stretch (phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


def build_w5_saturday() -> RunningWorkout:
    # Ф1 Нед5 Сб 24.10 — 4km w + 8x500m in 2:06 (p500m jog 2:30-2:38) + 2km c
    warmup = distance_step(1, 4000, StepType.WARMUP, "warmup")
    work = distance_step(1, 500, StepType.INTERVAL, "interval", pace_target(4 * 60 + 8, 4 * 60 + 16))
    recovery = distance_step(2, 500, StepType.RECOVERY, "recovery", pace_target(5 * 60, 5 * 60 + 15))
    repeats = create_repeat_group(iterations=8, workout_steps=[work, recovery], step_order=2)
    cooldown = distance_step(3, 2000, StepType.COOLDOWN, "cooldown")
    return RunningWorkout(
        workoutName="Phase1: 8x500m intervals",
        estimatedDurationInSecs=4300,
        description="4km warmup + 8x500m in 2:06 (~4:12/km), even splits, first rep 2:07-2:08 "
        "(500m jog 2:30-2:38 = 5:00-5:15/km, not faster) + 2km cooldown + stretch (phase_1_special_prep_1.md)",
        workoutSegments=[
            WorkoutSegment(segmentOrder=1, sportType=RUNNING_SPORT_TYPE, workoutSteps=[warmup, repeats, cooldown])
        ],
    )


WEEKS = {
    1: [
        ("2026-09-25", build_friday),
        ("2026-09-26", build_saturday),
        ("2026-09-27", build_sunday),
    ],
    2: [
        ("2026-09-29", build_w2_tuesday),
        ("2026-09-30", build_w2_thursday),
        ("2026-10-02", build_w2_friday),
        # Sat 03.10: 10k race replaces build_w2_saturday (10x500m)
        ("2026-10-04", build_w2_sunday),
    ],
    3: [
        ("2026-10-06", build_w3_tuesday),
        ("2026-10-08", build_w3_thursday),
        ("2026-10-09", build_w3_friday),
        ("2026-10-10", build_w3_saturday),
        ("2026-10-11", build_w3_sunday),
    ],
    4: [
        ("2026-10-13", build_w4_tuesday),
        ("2026-10-15", build_w4_thursday),
        ("2026-10-16", build_w3_friday),
        # Sat 17.10: couldn't run outside -> trainer bike replaces build_w4_saturday (12x600m)
        ("2026-10-17", build_w4_saturday_bike),
        ("2026-10-18", build_w3_sunday),
    ],
    # Recovery week, adjusted 19.10: wk4 was only ~35km run (Sat -> bike, Sun long run missed,
    # 2nd Sunday in a row), so Tue 10 -> 12km and Sun 12 -> 14km.
    5: [
        ("2026-10-20", build_w3_tuesday),
        ("2026-10-22", build_w5_thursday),
        ("2026-10-23", build_w3_friday),
        ("2026-10-24", build_w5_saturday),
        ("2026-10-25", build_w3_sunday),
    ],
}

# Week 1: workout_id of each workout already uploaded+scheduled by a prior run
# of this script (with Russian names) -- used by --update to rename them in
# place without touching their calendar schedule.
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
    week = int(sys.argv[sys.argv.index("--week") + 1]) if "--week" in sys.argv else 1
    WORKOUTS = WEEKS[week]

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
        upload = garmin.upload_cycling_workout if isinstance(workout, CyclingWorkout) else garmin.upload_running_workout
        uploaded = upload(workout)
        workout_id = uploaded.get("workoutId")
        if not workout_id:
            print(f"FAILED to upload {workout.workoutName}: {uploaded}")
            continue
        garmin.schedule_workout(workout_id, date_str)
        print(f"OK  {date_str}  {workout.workoutName}  (workout_id={workout_id})")


if __name__ == "__main__":
    main()
