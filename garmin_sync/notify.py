"""Telegram notifications for new signals (PLAN.md: "Notifications on new
signals -- not wired up yet"). Cheapest option per PLAN.md: ping a bot at
the end of the daily sync when `run_all_checks` finds something.

Needs a bot (via @BotFather) and its token, plus the chat id to send to
(your own DM with the bot, or a group it's in) -- see README.md.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(text: str) -> None:
    """Send `text` to TELEGRAM_CHAT_ID via the bot at TELEGRAM_BOT_TOKEN.

    Raises RuntimeError if either env var is missing, requests.HTTPError if
    the Telegram API rejects the call. Callers that consider notification
    failures non-fatal (e.g. daily_sync.py, which shouldn't fail an
    otherwise-successful sync over a bad chat id) should catch around this.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be set")

    response = requests.post(
        TELEGRAM_API_URL.format(token=token),
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()


def format_signals_message(day: str, signals: list[dict]) -> str:
    lines = [f"⚠️ {len(signals)} signal(s) for {day}:"]
    for s in signals:
        lines.append(f"- {s['signal_type']} ({s['severity']}): {s['detail']}")
    return "\n".join(lines)
