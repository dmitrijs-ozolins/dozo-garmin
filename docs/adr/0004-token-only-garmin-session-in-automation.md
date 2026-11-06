# ADR 0004: Token-only Garmin session in automation

- **Status:** Accepted
- **Date:** 2026-08-27 (recorded retroactively 2026-11-06)
- **Deciders:** Dmitrijs Ozolins

## Context

The daily sync runs unattended on GitHub Actions. Garmin increasingly
triggers CAPTCHA/anti-bot checks for logins from datacenter IPs, and CI
can't answer an MFA prompt. Garmin also rotates the refresh token on use.

## Options considered

1. **Username/password login on every run** (credentials as secrets).
   Simple, but likely to hit the CAPTCHA wall and can't handle MFA; also
   puts the raw password in CI.
2. **Log in once locally, resume from the stored session token in CI.**

## Decision

**Option 2.**

- `scripts/bootstrap_auth.py` logs in interactively once on a local
  machine (handles MFA) and writes the token JSON to
  `~/.dozo-garmin/garmin_tokens.json`, outside the repo.
- That JSON is stored as the `GARMIN_TOKENS` GitHub Actions secret.
- CI resumes from it via `login_from_env` and never falls back to a
  credential login — an MFA prompt in CI is a hard failure telling you to
  re-bootstrap.
- Because the refresh token rotates, the workflow re-uploads the current
  token to `GARMIN_TOKENS` after each run using `GH_SECRETS_PAT`, a
  fine-grained PAT scoped to this repo with Secrets: write only.

## Consequences

- No Garmin password in CI.
- Re-running the bootstrap roughly once a year (or when Garmin revokes the
  token) is scheduled manual maintenance.
- Only one consumer may own the token: two machines refreshing the same
  token invalidate each other.
- Expected to be superseded by the Mac mini move in
  [AUTOMATION_PLAN.md](../AUTOMATION_PLAN.md) step 4 — the sync runs from
  launchd on the mini with the local token file, and the secret
  re-upload/PAT go away. Record that as a new ADR when it happens.
