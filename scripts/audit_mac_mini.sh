#!/bin/zsh
# Read-only security audit of the Mac mini agent user (docs/MAC_MINI_SETUP.md §11).
#
# The agent user runs Claude Code and the GitHub Actions runner unattended, so
# anything that user can read could end up in a commit to this public repo.
# The boundary is macOS user permissions, not Claude's allow-list — this
# script checks that boundary from the agent's side (`sudo -u <agent>`).
#
# Run as the admin, from a copy the agent user can't modify (never from the
# agent's own checkout — root would run whatever the agent put there):
#   sudo zsh audit_mac_mini.sh [agent-user]
# Changes nothing. Exits 1 if any check FAILs.
set -u

AGENT=${1:-dozo.agent01}
[[ $EUID -eq 0 ]] || { print "Run with sudo (checks impersonate $AGENT)."; exit 2; }
id "$AGENT" >/dev/null 2>&1 || { print "No such user: $AGENT"; exit 2; }
AHOME=$(dscl . -read "/Users/$AGENT" NFSHomeDirectory | awk '{print $2}')

fails=0
pass() { print "PASS  $1" }
fail() { print "FAIL  $1"; (( fails++ )) }
warn() { print "WARN  $1" }
# allow <description> <cmd...>: PASS if the command succeeds
allow() { local d=$1; shift; if "$@" >/dev/null 2>&1; then pass "$d"; else fail "$d"; fi }
# deny <description> <cmd...>: PASS if the command fails
deny() { local d=$1; shift; if "$@" >/dev/null 2>&1; then fail "$d"; else pass "$d"; fi }
as_agent() { sudo -u "$AGENT" "$@" }
mode() { stat -f %Lp "$1" }
owner() { stat -f %Su "$1" }

print "== Account"
deny "$AGENT is not in admin" dseditgroup -o checkmember -m "$AGENT" admin
deny "$AGENT is not in wheel" dseditgroup -o checkmember -m "$AGENT" wheel
deny "$AGENT has no sudo rights" sh -c "sudo -n -l -U '$AGENT' | grep -q 'may run'"
deny "Guest user is off" sh -c \
  '[ "$(defaults read /Library/Preferences/com.apple.loginwindow GuestEnabled 2>/dev/null)" = 1 ]'

print "== Other users' data"
for d in /Users/*(/N); do
  [[ $d == /Users/Shared || $d == "$AHOME" || $d == /Users/Guest ]] && continue
  deny "$AGENT can't enter $d (mode $(mode "$d"))" as_agent test -x "$d"
done
allow "$AHOME is 700 (now $(mode "$AHOME"))" test "$(mode "$AHOME")" = 700
others=$(find /Users/Shared -mindepth 1 -maxdepth 1 ! -name '.*' ! -name 'SC Info' 2>/dev/null)
[[ -z $others ]] && pass "/Users/Shared is empty" || warn "/Users/Shared has files every user can see: ${others//$'\n'/, }"
deny "No volume mounted with 'Ignore ownership'" sh -c 'mount | grep -q noowners'

print "== System locations the admin runs code from"
for d in /Applications /Library /opt/homebrew /opt/homebrew/bin /usr/local /usr/local/bin; do
  [[ -e $d ]] || continue
  deny "$AGENT can't write $d" as_agent test -w "$d"
done

print "== Agent's own secrets"
for f in "$AHOME/.dozo-garmin/garmin_tokens.json" "$AHOME/Projects/dozo-garmin/.env" \
         "$AHOME/.ssh/id_ed25519" "$AHOME/actions-runner/.credentials"; do
  [[ -e $f ]] || continue
  allow "$f is 600 and owned by $AGENT (now $(mode "$f") $(owner "$f"))" \
    test "$(mode "$f")" = 600 -a "$(owner "$f")" = "$AGENT"
done
[[ -d $AHOME/.ssh ]] && allow "$AHOME/.ssh is 700" test "$(mode "$AHOME/.ssh")" = 700

print "== Machine"
allow "FileVault is on" sh -c 'fdesetup status | grep -q "FileVault is On"'
allow "Firewall is on" sh -c '/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate | grep -q enabled'
allow "Automatic security updates are on" sh -c \
  '[ "$(defaults read /Library/Preferences/com.apple.SoftwareUpdate CriticalUpdateInstall 2>/dev/null)" = 1 ]'

if lsof -nP -iTCP:22 -sTCP:LISTEN >/dev/null 2>&1; then
  ssh_users=$(dscl . -read /Groups/com.apple.access_ssh GroupMembership 2>/dev/null | cut -d' ' -f2-)
  [[ -n $ssh_users ]] && pass "Remote Login limited to: $ssh_users" \
    || fail "Remote Login is on for all users (Sharing → Remote Login → Only these users)"
  sshd -T 2>/dev/null | grep -qx 'passwordauthentication no' \
    && pass "SSH password login is off" || warn "SSH accepts passwords (§11 step 6)"
else
  pass "Remote Login is off"
fi
if lsof -nP -iTCP:5900 -sTCP:LISTEN >/dev/null 2>&1; then
  vnc_users=$(dscl . -read /Groups/com.apple.access_screensharing GroupMembership 2>/dev/null | cut -d' ' -f2-)
  [[ -n $vnc_users ]] && pass "Screen Sharing limited to: $vnc_users" \
    || fail "Screen Sharing is on for all users (Sharing → Screen Sharing → Only these users)"
else
  pass "Screen Sharing is off"
fi

print
(( fails == 0 )) && print "All checks passed." || { print "$fails check(s) failed — see docs/MAC_MINI_SETUP.md §11."; exit 1; }
