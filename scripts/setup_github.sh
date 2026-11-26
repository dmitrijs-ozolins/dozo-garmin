#!/bin/sh
# Create the issue labels and the GitHub Projects board from
# docs/adr/0007-github-issues-as-task-tracker.md. Safe to re-run (labels are
# upserted; the board is skipped if one with the same title exists).
#
# Usage:
#   scripts/setup_github.sh             # labels only
#   scripts/setup_github.sh --project   # labels + board
#                                       # (needs: gh auth refresh -s project)

set -eu

REPO="dmitrijs-ozolins/dozo-garmin"
OWNER="dmitrijs-ozolins"
BOARD_TITLE="dozo-garmin"

label() {
  gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force
}

label "type:feature"    "a2eeef" "New capability or change in behaviour"
label "type:bug"        "d73a4a" "Something works incorrectly"
label "type:chore"      "cfd3d7" "Maintenance, docs, training-plan updates"
label "type:analysis"   "d876e3" "Investigate and recommend; output is not code"
label "agent:analyze"   "fbca04" "Mac mini agent: post approach/spec for review"
label "agent:implement" "0e8a16" "Mac mini agent: implement and open a PR"

if [ "${1:-}" != "--project" ]; then
  exit 0
fi

number=$(gh project list --owner "$OWNER" --format json \
  --jq ".projects[] | select(.title == \"$BOARD_TITLE\") | .number")
if [ -z "$number" ]; then
  number=$(gh project create --owner "$OWNER" --title "$BOARD_TITLE" --format json --jq .number)
  gh project link "$number" --owner "$OWNER" --repo "$REPO"
fi

cat <<MSG
Board #$number: https://github.com/users/$OWNER/projects/$number
Finish in the UI (not scriptable via gh):
  1. Settings -> Status field options: Backlog, Analysis, Ready, In progress, In review, Done
  2. Workflows -> enable "Auto-add to project" (repo:$REPO), "Item closed" -> Done,
     "Pull request merged" -> Done
  3. Board view grouped by Status
MSG
