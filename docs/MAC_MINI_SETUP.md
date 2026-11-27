# Mac mini setup — agent user

Goal: chat with Claude Code running on the Mac mini from the phone
(Claude app via Remote Control, optionally Telegram) and have it update
the training schedule and push workouts to the Garmin calendar.

Runs as a dedicated macOS user, `dozo.agent01`, which commits and opens
PRs as a dedicated GitHub user, `dozo-agent01`. Steps marked **(admin)**
need the administrator account; everything else runs as `dozo.agent01`.
The repo lives at `~/Projects/dozo-garmin`.

Related: [AUTOMATION_PLAN.md](AUTOMATION_PLAN.md),
[ADR 0001](adr/0001-remote-task-execution-via-github-issues.md),
[ADR 0004](adr/0004-token-only-garmin-session-in-automation.md),
[ADR 0007](adr/0007-github-issues-as-task-tracker.md).

## 1. Machine prerequisites (admin)

1. Create the user: System Settings → Users & Groups → Add User →
   **Standard** account, name `dozo.agent01`. Then lock it down
   (section 11).
2. Keep the machine up (check first with `pmset -g`; often already set):
   ```bash
   sudo pmset -a sleep 0 autorestart 1
   ```
   `disksleep` only matters for spinning disks — leave it on an SSD.
3. Auto-login as `dozo.agent01` (Users & Groups → Automatically log in
   as). The Claude login lives in the agent's login keychain, which is
   only unlocked in a logged-in desktop session. Auto-login is not
   available while FileVault is on. Trade-off:
   - FileVault **on** (current choice): the disk is encrypted at rest
     (Garmin token, `.env`, local DB); after every reboot someone has to
     type the password before the Remote Control server starts. For a
     planned restart, `sudo fdesetup authrestart` reboots past the
     FileVault unlock screen once.
   - FileVault **off**: unattended recovery after power cuts and
     updates, but anyone with physical access to the mini can read the
     disk.
4. Command-line tools (Homebrew belongs to the admin account; the agent
   user can't `brew install`):
   ```bash
   xcode-select --install             # git
   brew install tmux
   ```
   `gh` is installed per user in step 2.
5. Optional, for copying files from the laptop: System Settings →
   General → Sharing → **Remote Login** on (allow `dozo.agent01` only).

## 2. Shell and per-user tools (agent)

Log in as `dozo.agent01` (Screen Sharing or locally) and open Terminal.

```bash
# Homebrew binaries (installed by admin) on PATH
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
exec zsh -l

# Python toolchain, per user (no admin needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Claude Code, native installer, per user
curl -fsSL https://claude.ai/install.sh | bash

# GitHub CLI, per user: official release binary into ~/.local/bin
V=$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["tag_name"].lstrip("v"))')
cd "$(mktemp -d)"
curl -fsSLO "https://github.com/cli/cli/releases/download/v$V/gh_${V}_macOS_arm64.zip"
curl -fsSLO "https://github.com/cli/cli/releases/download/v$V/gh_${V}_checksums.txt"
grep "gh_${V}_macOS_arm64.zip" "gh_${V}_checksums.txt" | shasum -a 256 -c
unzip -q "gh_${V}_macOS_arm64.zip" && cp "gh_${V}_macOS_arm64/bin/gh" ~/.local/bin/
cd ~

exec zsh -l
uv --version && claude --version && gh --version && tmux -V
```

## 3. GitHub access (agent)

The agent works as its own GitHub user, **`dozo-agent01`**, a
collaborator on this repo only. Its reach is limited by which repos it's
invited to, not by token scopes; its commits and PRs are clearly the
agent's; and you review and merge them as `dmitrijs-ozolins`.

1. As `dmitrijs-ozolins`: repo → Settings → Collaborators → invite
   `dozo-agent01` with the **Write** role (not Maintain/Admin); accept
   the invite as `dozo-agent01`.
2. SSH key for git (on the mini, as `dozo.agent01`): `ssh-keygen -t
   ed25519`, add `~/.ssh/id_ed25519.pub` to `dozo-agent01` → Settings →
   SSH and GPG keys. First connection — check the fingerprint matches
   GitHub's published ED25519 one
   (`SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`):
   ```bash
   ssh -T git@github.com        # "Hi dozo-agent01! ..."
   ```
3. `gh` for issues and PRs (the API needs its own login; SSH only covers
   git):
   ```bash
   gh auth login     # GitHub.com → SSH → skip key upload → web browser,
                     # approve signed in as dozo-agent01 (private window)
   gh auth status    # dozo-agent01, git protocol ssh
   ```
   The browser login always includes `repo`, `read:org` and `gist`, plus
   `admin:public_key` when SSH is chosen. To drop the extras, use a
   classic PAT on `dozo-agent01` with only `repo` + `read:org`
   (`gh auth login --with-token`) and revoke the GitHub CLI OAuth app.
   Fine-grained PATs don't help here: they can't reach another user's
   repo through a collaborator invite.
4. Commit identity — `dozo-agent01`'s no-reply address (its Settings →
   Emails, or `gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"'`):
   ```bash
   git config --global user.name  "dozo-agent01"
   git config --global user.email "347342578+dozo-agent01@users.noreply.github.com"
   ```

Optional hardening: a repository ruleset on `master` requiring PRs, with
a bypass for the admin role (so your own laptop pushes still work). The
agent's commits then can only reach `master` through a PR.

## 4. Repo and Python env (agent)

```bash
mkdir -p ~/Projects && cd ~/Projects
git clone git@github.com:dmitrijs-ozolins/dozo-garmin.git
cd dozo-garmin
git config core.hooksPath .githooks     # issue ref in every commit (ADR 0007)

uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
.venv/bin/python -c 'import pydantic, garminconnect'   # both must import
```

`.venv` must be a directory — an editor can leave an empty `.venv`
*file* behind, which `uv venv` won't replace (`rm .venv` first).
`pydantic` comes from the `garminconnect[workout]` extra; without it
`push_week_runs.py` fails with `ExecutableStep() takes no arguments`.

## 5. Secrets (agent)

`.env` (`DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) is
never in git. Create it from the template and fill in the values (or
copy the laptop's with AirDrop / `scp` if the mini should share the
laptop's database):

```bash
cd ~/Projects/dozo-garmin
cp .env.example .env && chmod 600 .env
```

Only the database and Telegram scripts need it; pushing workouts to
Garmin doesn't. The agent can't read it (deny rule in step 7.3).

## 6. Garmin login (agent)

Log in **fresh** on the mini — don't copy the laptop's token file. A
separate login is a separate session, so the mini, the laptop and the
GitHub Actions secret don't invalidate each other's refresh tokens
(ADR 0004).

```bash
cd ~/Projects/dozo-garmin
.venv/bin/python scripts/bootstrap_auth.py      # email, password, MFA code
chmod 600 ~/.dozo-garmin/garmin_tokens.json
```

Ignore the script's closing hint to run `gh secret set GARMIN_TOKENS` —
that would overwrite the GitHub Actions session with the mini's.

Verify without writing anything to Garmin. The dry run only builds the
workouts (it never logs in), so check the token separately:

```bash
.venv/bin/python scripts/push_week_runs.py --week 8 --dry-run
.venv/bin/python -c 'from garminconnect import Garmin
from garmin_sync.auth import DEFAULT_TOKENSTORE
g = Garmin(); g.login(str(DEFAULT_TOKENSTORE)); print("token OK")'
```

(Use the latest week number in `WEEKS` in `scripts/push_week_runs.py`.)

## 7. Claude Code (agent)

### 7.1 Login and trust

```bash
cd ~/Projects/dozo-garmin
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
phone. Machine-local file, ignored by `.gitignore` (check `git status`
stays clean afterwards). The `Read` deny rules also stop Claude from
writing those files. To approve each real Garmin write from the phone,
narrow the first rule to `push_week_runs.py --dry-run:*`.

```bash
cat > ~/Projects/dozo-garmin/.claude/settings.local.json <<'EOF'
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
cd ~/Projects/dozo-garmin
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
cd ~/Projects/dozo-garmin
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
cd ~/Projects/dozo-garmin && claude
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

## 10. GitHub Actions runner: issue label → work on the mini

Review issues on GitHub (web or mobile app) and add a label; the mini
picks it up ([`.github/workflows/agent.yml`](../.github/workflows/agent.yml),
ADR 0001 option 3b):

| Label you add | What the mini does |
|---|---|
| `agent:analyze` | Reads the issue and code, posts a proposed approach + numbered questions as an issue comment. No file changes. |
| `agent:implement` | Implements on branch `<issue>-<slug>`, commits, pushes, opens a PR `Closes #N`, links it on the issue. |

The label is removed when the run ends (success or failure), so adding it
again re-runs. Only labels you add, on issues you opened, count; runs
queue one at a time. The repo is public, so anyone can comment: Claude
sees the issue body and only your comments and earlier agent output.
For someone else's issue, copy what you want into a new issue of your own.

Typical flow: write the issue → `agent:analyze` → answer its questions in
a comment (or edit the issue) → `agent:implement` → review the PR →
merge. Comments on the issue take precedence over the original text.
Feedback on a PR: comment on the issue and add `agent:implement` again —
it continues on the same branch and comments on the open PR.

### 10.1 Install the runner (agent)

1. On github.com: repo → Settings → Actions → Runners → **New
   self-hosted runner** → macOS, ARM64. Keep the page open — it shows
   the download URL and a one-time registration token.
2. On the mini, as `agent`:
   ```bash
   mkdir -p ~/actions-runner && cd ~/actions-runner
   # download + extract: copy the two commands (curl …, tar xzf …) from the GitHub page
   ./config.sh --url https://github.com/dmitrijs-ozolins/dozo-garmin \
     --token <token from the page> \
     --name mac-mini --labels dozo-agent --unattended
   ```
3. Give the runner the same PATH as your login shell (it needs `claude`,
   `uv` and `gh`, which live in `~/.local/bin` / Homebrew):
   ```bash
   zsh -lc 'echo $PATH' > ~/actions-runner/.path
   ```
4. Run it as a service. On macOS `svc.sh` installs a **LaunchAgent**, so
   it runs inside the auto-logged-in `agent` session with the unlocked
   keychain — that's where the Claude login lives:
   ```bash
   ./svc.sh install && ./svc.sh start && ./svc.sh status
   ```
   Settings → Actions → Runners should show `mac-mini` as **Idle**.

### 10.2 Repo settings (once, on github.com)

- Settings → Actions → General → **Fork pull request workflows from
  outside collaborators** → *Require approval for all outside
  collaborators*. The agent workflow never runs on PRs anyway; this
  keeps it that way for any future workflow.
- Same page → **Workflow permissions**: leave *Read repository contents*
  as the default — `agent.yml` requests its own write permissions.

### 10.3 First test

1. Open a throwaway issue, e.g. "Agent smoke test: list the ADRs in a
   comment", add `agent:analyze`.
2. Within a minute: a "🤖 started" comment, then the analysis comment;
   the label disappears. Run log: repo → Actions → *Mac mini agent*.
3. Then the real one: #10 → `agent:analyze` first.

What the runner's Claude may do: read/edit files in its own checkout
(`~/actions-runner/_work/…`, separate from `~/Projects/dozo-garmin`, so it
doesn't collide with the Remote Control session), `git add/commit`,
`py_compile` / `pytest`, and Garmin scripts with
`--dry-run` only. Pushing, PRs and real Garmin writes are done by the
fixed workflow steps or by you.

## 11. Lock down the agent user (admin)

`dozo.agent01` runs Claude unattended (`acceptEdits`, the runner) on
instructions that arrive from GitHub and the phone. Assume anything that
user can read, a confused or prompt-injected agent can read too and
commit to this **public** repo. Claude's allow/deny rules (step 7.3) only
narrow what Claude does. The real boundary is macOS user permissions, so
set them as if the agent were an untrusted user.

1. **No admin rights.** It must be a Standard account (step 1). Check
   with `dseditgroup -o checkmember -m dozo.agent01 admin`. If it's an
   admin, remove it with
   `sudo dseditgroup -o edit -d dozo.agent01 -t user admin`. Never add it
   to `admin` "to make brew work".
2. **Close every other home folder.** macOS creates home folders as
   `755`. Any user can then list them and read the files at their top
   level, such as `~/.zshrc`, `~/.gitconfig` and anything saved straight
   into the home folder. `750` isn't enough, because all users share the
   `staff` group. Repeat for every user except the agent:
   ```bash
   sudo chmod 700 /Users/<admin>             # each other user
   sudo chmod 700 /Users/dozo.agent01        # and the agent's own
   ```
   Desktop, Documents, Downloads and Library are already `700` inside.
   The only side effect is that other users lose access to that user's
   `~/Public` Drop Box.
3. **No shared spots for data.** Every user can read `/Users/Shared`,
   `/tmp` and any external drive set to *Ignore ownership on this volume*
   (Finder → Get Info). Don't put files you want kept from the agent
   there. Copy files to the agent over `scp` or AirDrop into its own home
   folder.
4. **Keep the admin's tools admin-owned.** The agent must not be able to
   write to `/opt/homebrew` or `/Applications`. Otherwise it could
   replace a binary that the admin later runs, and the next `brew` run
   would execute the agent's code as the admin. Don't `chown` them to the
   agent.
5. **No admin or personal credentials on the agent's side.**
   - Give the admin a different password from the agent.
   - Don't type the admin password in the agent's session.
   - Don't copy the admin's or laptop's SSH keys, `gh` login or PATs
     into it.
   - The agent acts only as `dozo-agent01`, a Write collaborator on this
     repo (step 3). Its GitHub reach is that, and nothing of
     `dmitrijs-ozolins`'s.
6. **Remote access only for whom it's needed.**
   - System Settings → General → Sharing: **Remote Login** and **Screen
     Sharing** → *Only these users*, or turn them off.
   - With Remote Login on, use key-only SSH. Add your laptop's public
     key to the target user's `~/.ssh/authorized_keys` **first**, then
     turn off password login:
     ```bash
     printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\n' \
       | sudo tee /etc/ssh/sshd_config.d/100-no-passwords.conf
     sudo launchctl kickstart -k system/com.openssh.sshd
     ```
7. **Machine basics.**
   - Firewall on: System Settings → Network → Firewall.
   - Guest User off: Users & Groups.
   - FileVault on (step 1).
   - Automatic updates: Software Update → *Install Security Responses
     and system files* on.
8. **No extra privacy grants.** Under Privacy & Security, don't grant
   Full Disk Access, Accessibility or Screen Recording to Terminal,
   `claude` or the runner in the agent's session. Nothing in this setup
   needs them.

What stays visible by design:
- `ps` shows every user's processes and their command lines, so never
  pass secrets as arguments in the admin's session.
- System files and `/Applications` stay readable.

Optional extra layer: Claude Code's `/sandbox` (Seatbelt on macOS) also
confines the agent's own Bash commands. Points 1–4 hold regardless.

### 11.1 Verify

[`scripts/audit_mac_mini.sh`](../scripts/audit_mac_mini.sh) is read-only.
It runs each check *as the agent*, for example "can `dozo.agent01` enter
`/Users/<admin>`?", and prints PASS / FAIL / WARN. Run it as the admin from
a copy the agent can't edit. Never run it from `~dozo.agent01/Projects/…`:
under `sudo`, root would execute whatever the agent put in that file.

```bash
# as the admin
curl -fsSLo ~/audit_mac_mini.sh \
  https://raw.githubusercontent.com/dmitrijs-ozolins/dozo-garmin/master/scripts/audit_mac_mini.sh
less ~/audit_mac_mini.sh          # read it before running it as root
sudo zsh ~/audit_mac_mini.sh      # default user: dozo.agent01
```

Rerun it after adding a user, macOS upgrades and changes to Sharing.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `claude remote-control` exits with a login error | `claude` → `/login` with the subscription account (API keys aren't supported) |
| `Workspace not trusted` when started from Login Items | Run `claude` once interactively in the folder and trust it |
| Session doesn't appear on the phone after reboot | Agent user not auto-logged in (FileVault?) or the login item didn't run — check `tmux ls` |
| Garmin asks for MFA / 401 | Token expired or revoked — rerun `scripts/bootstrap_auth.py` |
| Commit rejected: "no issue reference" | Branch name must start with the issue number, e.g. `1-progress-log` |
| `git push` asks for credentials | Remote is HTTPS — `git remote set-url origin git@github.com:dmitrijs-ozolins/dozo-garmin.git` |
| `Host key verification failed` | First SSH connection — run `ssh -T git@github.com` and check the fingerprint (step 3) |
| `brew install` → permission denied | Homebrew belongs to the admin account — install as admin, or per user (gh: step 2) |
| `ExecutableStep() takes no arguments` | `pydantic` missing — reinstall `requirements.txt` (step 4) |
| `gh` not found from Claude | Claude's shell doesn't read `~/.zprofile`; use `~/.local/bin/gh` |
| Labelled issue, nothing happens | Runner offline (Settings → Actions → Runners), the label was added by someone else / by a bot, or the issue wasn't opened by you |
| Runner job: `claude: command not found` | Rewrite `~/actions-runner/.path` (step 10.1.3), then `./svc.sh stop && ./svc.sh start` |
| Runner job: Claude login / 401 errors | Runner not running in the logged-in GUI session — reinstall with `./svc.sh install` as `agent`, check auto-login |
