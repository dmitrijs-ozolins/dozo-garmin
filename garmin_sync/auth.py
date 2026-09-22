"""Garmin Connect auth (see PLAN.md, Phase 0 and the CAPTCHA/anti-bot note).

`garminconnect` (>=0.3) no longer depends on the (now-deprecated) `garth`
package — it ships its own token store: a single small JSON blob
(refresh-token pair), loadable from a file path *or* directly from a JSON
string. That's what makes it a good fit for a GitHub Actions secret: no
directory-tarball/base64 dance like PLAN.md's original garth-based sketch.

Two entry points:
  * `login_interactive` — Phase 0 bootstrap and any local run. Prompts for
    credentials/MFA the first time, then reuses the cached token file.
  * `login_from_env` — CI. Resumes from a token JSON string (the
    GARMIN_TOKENS secret) and never falls back to a fresh username/password
    login, since that's exactly what risks the datacenter-IP CAPTCHA wall.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path

from garminconnect import Garmin

# Outside the repo on purpose — never something that could get committed.
DEFAULT_TOKENSTORE = Path.home() / ".dozo-garmin" / "garmin_tokens.json"


def _prompt_mfa() -> str:
    return input("Enter the MFA code Garmin just sent you: ").strip()


def login_interactive(
    tokenstore: str = str(DEFAULT_TOKENSTORE),
    email: str | None = None,
    password: str | None = None,
) -> Garmin:
    """Local, interactive login. Reuses a cached, still-valid token at
    `tokenstore`; otherwise prompts for credentials + MFA and writes fresh
    tokens there. Never use this in CI.
    """
    email = email or os.environ.get("GARMIN_EMAIL") or input("Garmin email: ").strip()
    password = password or os.environ.get("GARMIN_PASSWORD") or getpass.getpass("Garmin password: ")

    garmin = Garmin(email, password, prompt_mfa=_prompt_mfa)
    garmin.login(tokenstore=tokenstore)
    return garmin


def login_from_env(env_var: str = "GARMIN_TOKENS") -> Garmin:
    """Non-interactive login for CI: resumes from a token JSON blob in an
    env var (the GARMIN_TOKENS secret). Deliberately does not fall back to
    a credential login — CI has no MFA input and hitting the SSO login
    endpoint from a datacenter IP is exactly what PLAN.md flags as the
    CAPTCHA risk to avoid.
    """
    tokenstore = os.environ.get(env_var)
    if not tokenstore:
        raise RuntimeError(
            f"${env_var} is not set. Run `python scripts/bootstrap_auth.py` "
            "locally and set the result as the GARMIN_TOKENS GitHub secret."
        )

    def _no_mfa_in_ci() -> str:
        raise RuntimeError(
            "Garmin is asking for an MFA code, which means the cached "
            "session has expired or been revoked. This can't be answered "
            "from CI — re-run `python scripts/bootstrap_auth.py` locally "
            "and update the GARMIN_TOKENS secret."
        )

    garmin = Garmin(prompt_mfa=_no_mfa_in_ci)
    garmin.login(tokenstore=tokenstore)
    return garmin


def dump_tokens(garmin: Garmin) -> str:
    """Current token JSON for this session (may differ from what was passed
    in if Garmin rotated the refresh token during this run) — see
    scripts/daily_sync.py, which re-uploads this to the GARMIN_TOKENS
    secret via the PAT-based flow.
    """
    return garmin.client.dumps()
