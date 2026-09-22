#!/usr/bin/env python3
"""Phase 0 — one-time interactive Garmin login (PLAN.md).

Run this locally, never in CI: logs in with your Garmin credentials,
handles MFA if enabled, and writes a small session-token file. Also used
for local runs of scripts/daily_sync.py, which reuse the same cached token.

Usage:
    python scripts/bootstrap_auth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin_sync.auth import DEFAULT_TOKENSTORE, login_interactive


def main() -> None:
    DEFAULT_TOKENSTORE.parent.mkdir(parents=True, exist_ok=True)
    garmin = login_interactive(str(DEFAULT_TOKENSTORE))

    print(f"\nLogged in as {garmin.full_name or garmin.display_name}.")
    print(f"Session tokens saved to: {DEFAULT_TOKENSTORE}\n")
    print("Next: set this as the GARMIN_TOKENS GitHub Actions secret so the")
    print("daily sync workflow can use it without your password:\n")
    print(f"    gh secret set GARMIN_TOKENS < {DEFAULT_TOKENSTORE}\n")
    print("(Or paste the file's contents into Settings -> Secrets and")
    print("variables -> Actions -> New repository secret.)\n")
    print("You'll also need a fine-grained PAT scoped to this repo with")
    print("'Secrets: write' permission, stored as a GH_SECRETS_PAT secret --")
    print("the daily workflow uses it to rewrite GARMIN_TOKENS whenever")
    print("Garmin rotates the refresh token. See README.md.")


if __name__ == "__main__":
    main()
