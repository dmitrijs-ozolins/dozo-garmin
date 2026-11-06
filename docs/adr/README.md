# Architecture Decision Records

One file per decision: `NNNN-short-title.md`, numbered in order and never
renumbered. Each record has Status, Date, Context, Options considered,
Decision, and Consequences. A decision that's later replaced stays in
place with status `Superseded by ADR NNNN`.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-remote-task-execution-via-github-issues.md) | Remote task execution via GitHub issues and Claude Code action on a self-hosted Mac mini runner | Accepted |
| [0002](0002-python-garminconnect-as-single-data-source.md) | python-garminconnect as the single Garmin data source | Accepted |
| [0003](0003-health-data-in-external-postgres.md) | Health data in external Postgres, not in the public repo | Accepted |
| [0004](0004-token-only-garmin-session-in-automation.md) | Token-only Garmin session in automation | Accepted |
| [0005](0005-separate-detection-from-plan-adjustment.md) | Separate anomaly detection from plan adjustment | Accepted |
| [0006](0006-telegram-notifications.md) | Telegram for notifications | Accepted |

0002–0006 were recorded retroactively from [PLAN.md](../PLAN.md) and the
module docstrings; their dates are when the decision was made.
