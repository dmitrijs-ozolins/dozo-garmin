# Mac mini setup — agent user

Goal: chat with Claude Code running on the Mac mini from the phone
(Claude app via Remote Control, optionally Telegram) and have it update
the training schedule and push workouts to the Garmin calendar.

Runs as a dedicated macOS user, `agent` below. Steps marked **(admin)**
need an administrator account; everything else runs as `agent`.

Related: [AUTOMATION_PLAN.md](AUTOMATION_PLAN.md),
[ADR 0001](adr/0001-remote-task-execution-via-github-issues.md),
[ADR 0004](adr/0004-token-only-garmin-session-in-automation.md),
[ADR 0007](adr/0007-github-issues-as-task-tracker.md).

## 1. Machine prerequisites (admin)

1. Create the user: System Settings → Users & Groups → Add User →
   **Standard** account, name `agent`.
2. Keep the machine up:
   ```bash
   sudo pmset -a sleep 0 disksleep 0 autorestart 1
   ```
3. Auto-login as `agent` (Users & Groups → Automatically log in as →
   `agent`). The Claude login lives in the agent's login keychain, which
   is only unlocked in a logged-in desktop session. Auto-login is not
   available while FileVault is on — either turn FileVault off on this
   machine, or accept typing the password after every reboot.
4. Command-line tools, shared by all users:
   ```bash
   xcode-select --install             # git
   brew install gh tmux               # Homebrew lives in the admin account
   ```
5. Optional, for copying `.env` from the laptop: System Settings →
   General → Sharing → **Remote Login** on (allow `agent`).

## 2. Shell and per-user tools (agent)

Log in as `agent` (Screen Sharing or locally) and open Terminal.

```bash
# Homebrew binaries (installed by admin) on PATH
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
exec zsh -l

# Python toolchain, per user (no admin needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Claude Code, native installer, per user
curl -fsSL https://claude.ai/install.sh | bash

exec zsh -l
uv --version && claude --version && gh --version && tmux -V
```

## 3. GitHub access (agent)

Use a **fine-grained personal access token** scoped to this repo only,
not a full `gh auth login` — the agent then can't touch anything else
on the account.

1. On github.com (as dmitrijs-ozolins): Settings → Developer settings →
   Fine-grained tokens → Generate. Repository access: **only
   `dozo-garmin`**. Permissions: Contents **Read and write**, Pull
   requests **Read and write**, Issues **Read and write** (Metadata
   read-only is added automatically). Expiry: 1 year, put a reminder in
   the calendar.
2. On the mini:
   ```bash
   gh auth login --with-token    # paste the token, then Ctrl-D
   gh auth setup-git             # git push over https uses gh's token
   gh auth status
   ```
3. Commit identity — mark agent commits so they're distinguishable in
   history (GitHub no-reply address, links commits to the account):
   ```bash
   git config --global user.name  "Dmitrijs Ozolins (mac mini agent)"
   git config --global user.email "6238225+dmitrijs-ozolins@users.noreply.github.com"
   ```

Optional hardening: a repository ruleset on `master` requiring PRs, with
a bypass for the admin role (so your own laptop pushes still work). The
agent's commits then can only reach `master` through a PR.

## 4. Repo and Python env (agent)

```bash
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/dmitrijs-ozolins/dozo-garmin.git
cd dozo-garmin
git config core.hooksPath .githooks     # issue ref in every commit (ADR 0007)

uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
```

## 5. Secrets (agent)

`.env` (`DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) is
never in git. Copy it from the laptop, either AirDrop, or with Remote
Login on:

```bash
# on the laptop
scp ~/projects/dozo-garmin/.env agent@<mini-hostname>.local:~/projects/dozo-garmin/.env
```

```bash
# on the mini
chmod 600 ~/projects/dozo-garmin/.env
```

## 6. Garmin login (agent)

Log in **fresh** on the mini — don't copy the laptop's token file. A
separate login is a separate session, so the mini, the laptop and the
GitHub Actions secret don't invalidate each other's refresh tokens
(ADR 0004).

```bash
cd ~/projects/dozo-garmin
.venv/bin/python scripts/bootstrap_auth.py      # email, password, MFA code
ls -l ~/.dozo-garmin/garmin_tokens.json
```

Verify without writing anything to Garmin:

```bash
.venv/bin/python scripts/push_week_runs.py --week 8 --dry-run
```

(Use the latest week number in `WEEKS` in `scripts/push_week_runs.py`.)

## 7. Claude Code (agent)

### 7.1 Login and trust

```bash
cd ~/projects/dozo-garmin
claude          # /login → claude.ai subscription account; trust the folder; then /exit
```

### 7.2 Agent-user instructions

The laptop's Claude memory doesn't exist here. Put the mini-specific
rules in the agent user's global `CLAUDE.md` (machine-local, not in the
repo):

```bash
mkdir -p ~/.claude
cat > ~/.claude/CLAUDE.md <<'EOF'
# Mac mini agent

- Always reply in English.
- Training conversations (analysing runs, progress log, plan changes,
  syncing weeks to Garmin): commit the changes yourself without asking.
  Scope: training_plan/ and workout builders / WEEKS in
  scripts/push_week_runs.py.
  - Branch `<issue>-<slug>` off an up-to-date master (git pull first);
    standing issue #1 "Training plan & log updates" unless a specific
    issue exists. If an open PR branch for #1 exists, add commits to it.
  - Commit only the files you changed (`git commit -- <paths>`); the
    commit-msg hook appends (#N).
  - Push the branch, open a PR with `Refs #1` (or `Closes #N` for a
    specific issue), switch back to master. Never push to master.
  - No personal reasons for missed sessions or raw health data in
    committed text — the repo is public.
- Before any real Garmin write, run the same command with --dry-run and
  show what will change; then run it for real.
- Reply with the PR link and what was pushed to the Garmin calendar.
EOF
```

### 7.3 Pre-approved commands

So a permission prompt doesn't stall the session while you're on the
phone. Machine-local file, not committed (check `git status` stays
clean afterwards):

```bash
cat > ~/projects/dozo-garmin/.claude/settings.local.json <<'EOF'
{
  "permissions": {
    "allow": [
      "Bash(.venv/bin/python scripts/push_week_runs.py:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git pull:*)",
      "Bash(git fetch:*)",
      "Bash(git switch:*)",
      "Bash(git checkout:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git push -u origin:*)",
      "Bash(git push origin:*)",
      "Bash(gh issue list:*)",
      "Bash(gh issue view:*)",
      "Bash(gh pr list:*)",
      "Bash(gh pr view:*)",
      "Bash(gh pr create:*)"
    ],
    "deny": [
      "Bash(git push origin master:*)",
      "Bash(git push --force:*)",
      "Bash(git push -f:*)",
      "Read(./.env)",
      "Read(~/.dozo-garmin/**)"
    ]
  }
}
EOF
```

File edits are covered by starting the server in `acceptEdits` mode
(next step). Anything not listed still asks — approve it from the phone.

### 7.4 Remote Control server

Start it from Terminal **in the agent's desktop session** (not over
SSH — the keychain with the Claude login must be unlocked):

```bash
cd ~/projects/dozo-garmin
tmux new-session -A -s claude \
  "claude remote-control --name dozo-garmin --permission-mode acceptEdits"
```

First run asks `Enable Remote Control? (y/n)` → `y`, and possibly the
spawn mode → `1` (`same-dir`; worktrees wouldn't have `.venv` / `.env`).
Press space for a QR code. Detach with `Ctrl-b d`; reattach with
`tmux attach -t claude`.

Start it automatically after reboot / auto-login:

```bash
mkdir -p ~/bin
cat > ~/bin/claude-rc.command <<'EOF'
#!/bin/zsh -l
cd ~/projects/dozo-garmin
exec tmux new-session -A -s claude \
  "claude remote-control --name dozo-garmin --permission-mode acceptEdits"
EOF
chmod +x ~/bin/claude-rc.command
```

System Settings → General → Login Items → **+** →
`~/bin/claude-rc.command`. It opens Terminal at login and starts (or
reattaches to) the server.

If the server was stopped, `claude remote-control` in the same folder
within ~4 hours brings the previous sessions back.

## 8. Phone

1. Claude app → **Code** → the `dozo-garmin` session from the mini (or
   scan the QR code).
2. Test read-only first:
   > Show week 8 from push_week_runs.py and what's currently scheduled in
   > Garmin for this week. Don't change anything.
3. Then a real change:
   > Move Thursday's hills to Friday, dry-run first, then push to Garmin
   > and open the PR.

Usage counts against the same Claude subscription limits as the laptop.

## 9. Optional: Telegram instead of / next to the Claude app

Official channel plugin (research preview, needs [Bun](https://bun.sh)):

```bash
curl -fsSL https://bun.sh/install | bash && exec zsh -l
cd ~/projects/dozo-garmin && claude
```

In Claude Code:

```
/plugin install telegram@claude-plugins-official      # scope: user
/telegram:configure <bot token from @BotFather>
/exit
```

Run with the channel (instead of, or in a second tmux window next to,
the Remote Control server):

```bash
claude --channels plugin:telegram@claude-plugins-official --permission-mode acceptEdits
```

Message the bot → it replies with a pairing code →
`/telegram:access pair <code>` → `/telegram:access policy allowlist`.

The existing sync-alert bot (`garmin_sync/notify.py`) only sends, so it
can be reused for the channel — alerts and replies then share one chat.
A separate bot keeps them apart.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `claude remote-control` exits with a login error | `claude` → `/login` with the subscription account (API keys aren't supported) |
| `Workspace not trusted` when started from Login Items | Run `claude` once interactively in the folder and trust it |
| Session doesn't appear on the phone after reboot | Agent user not auto-logged in (FileVault?) or the login item didn't run — check `tmux ls` |
| Garmin asks for MFA / 401 | Token expired or revoked — rerun `scripts/bootstrap_auth.py` |
| Commit rejected: "no issue reference" | Branch name must start with the issue number, e.g. `1-progress-log` |
| `git push` asks for credentials | `gh auth setup-git`; token expired → generate a new fine-grained token |
