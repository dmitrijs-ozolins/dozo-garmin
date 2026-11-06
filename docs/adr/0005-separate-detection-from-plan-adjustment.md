# ADR 0005: Separate anomaly detection from plan adjustment

- **Status:** Accepted
- **Date:** 2026-08-27 (recorded retroactively 2026-11-06)
- **Deciders:** Dmitrijs Ozolins

## Context

The point of the sync is to adjust the training plan when something goes
wrong: a missed workout, bad sleep, a resting-HR spike, an injury. That
involves two different kinds of logic — noticing that something happened,
and deciding what to change in the plan.

## Decision

Keep them as separate modules with a data contract in between.

- **Detect:** `garmin_sync/signals.py` runs after each sync and writes
  structured rows to the `signals` table (missed session, low sleep score,
  resting-HR spike, active injury flag). It never changes the plan.
- **Decide:** a future plan-adjuster consumes `signals` and proposes or
  applies plan changes. Not built yet.

Injury can't come from Garmin, so it's a manual input
(`scripts/plan_cli.py add-injury`) that detection reads like any other
source.

## Consequences

- Detection is simple, testable and useful on its own (e.g. Telegram
  alerts, [ADR 0006](0006-telegram-notifications.md)).
- The adjuster can be swapped or evolved — rules, or Claude generating the
  next week (option (b) in [AUTOMATION_PLAN.md](../AUTOMATION_PLAN.md)
  step 5) — without touching detection.
- Thresholds live in detection; adjustment policy lives in the adjuster.
  Changes to one shouldn't require changes to the other.
