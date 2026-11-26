# dozo-garmin

Shared project instructions (also used by GitHub Copilot):

@../.github/copilot-instructions.md

## Claude-specific

### Git

Issue → PR workflow ([ADR 0001](../docs/adr/0001-remote-task-execution-via-github-issues.md),
running on the Mac mini's self-hosted runner): work on a new branch,
commit there, and open a PR whose description contains `Closes #N`
(the PR-link check doesn't run on PRs opened by the workflow token, so
this is on you). Never push to `master`.

### Language

Code, docs and commit messages in English.
