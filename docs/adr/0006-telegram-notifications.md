# ADR 0006: Telegram for notifications

- **Status:** Accepted
- **Date:** 2026-09-28 (recorded retroactively 2026-11-06)
- **Deciders:** Dmitrijs Ozolins

## Context

New signals ([ADR 0005](0005-separate-detection-from-plan-adjustment.md))
are only useful if someone sees them soon after the daily sync.

## Options considered

Slack, Pushover, email, Telegram bot.

## Decision

**Telegram bot.** `garmin_sync/notify.py` sends a message at the end of
`scripts/daily_sync.py` when `run_all_checks` finds something.
Credentials are `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`.

## Consequences

- Free, a plain HTTPS call, no extra dependency beyond `requests`, and
  already on the phone.
- Best-effort: missing config skips notifying, and a send failure is
  logged without failing the sync.
- Available as the channel for other alerts too (e.g. automation failures
  on the Mac mini, token needing re-bootstrap).
