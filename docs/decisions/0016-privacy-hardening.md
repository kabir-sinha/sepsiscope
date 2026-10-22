# 0016 — Privacy hardening: UTC commits, local denylist, git hooks, privacy-audit

**Date:** 2026-10-22 · **Status:** Accepted · **Does not change** `docs/protocol.md`

## Context
A full read-only audit before Phase 2 found no secrets, home paths, foreign emails or
data in the repository or its history, but it did find personal context: account-tier
wording, the maintainer's name outside the copyright notice, references to other
projects, machine-specific setup notes, working-habit notes in `CLAUDE.md`, and the local
timezone offset stored in every commit. The old guard only checked macOS home paths,
emails, data files, file size and PNG metadata, and it never looked at commit messages or
timestamps.

## Decision
- **Name policy.** The maintainer's name appears only in the README copyright line, the
  `pyproject.toml` author field and the git author. Elsewhere: "the maintainer".
- **Local notes.** Personal working notes live in `CLAUDE.local.md`, which Claude Code
  loads next to `CLAUDE.md` and which is gitignored
  ([Claude Code memory docs](https://code.claude.com/docs/en/memory)).
- **UTC commits.** Every git command runs with `TZ=UTC`, so author and committer offsets
  are `+0000`. Contributors can add the repo-local alias
  `git config --local alias.c '!TZ=UTC git commit'`. Pull requests are merged locally
  (Dependabot updates as a local squash), never in the web interface, because a web merge
  stores the browser's offset.
- **Rules in one place.** `src/sepsiscope/audit/` holds all rules; the pre-commit hook,
  the git hooks, CI and `sepsiscope privacy-audit` call it. New generic rules: Linux and
  Windows home paths, account-tier wording, enrollment-ID shapes, notebook outputs and
  metadata (only `kernelspec` and `language_info` without `version`). Lockfiles are exempt
  from the wording and ID rules (hashes would false-alarm), never from path or email rules.
- **Local denylist.** `.privacy-denylist.local` (gitignored, mode 600) lists personal
  values, one per line. It is read only when present, so CI uses generic patterns only.
  Plaintext salted hashes were rejected: a name has too little entropy to stay secret.
- **Git hooks** (pre-commit `default_install_hook_types`): `commit-msg` rejects
  `Co-Authored-By` (except GitHub bot co-authors), AI-tool trailers, "generated with"
  lines, chat session URLs and personal values; `pre-push` checks every outgoing commit
  for `+0000` offsets, allowed identities and a clean message. CI runs the same check on
  the pushed range (`before..sha`, or `base..head` for pull requests). Commits authored by
  GitHub bots are exempt from the offset rule; their timestamps come from GitHub.
- **`sepsiscope privacy-audit`** scans tracked files, every blob in history, messages,
  identities, offsets and ref names, and prints masked output only. Findings that exist
  only in commits before 2026-10-22 are reported as *known* and do not fail the run until
  the pre-sharing history rewrite; after it, `--strict` becomes the default.

## Alternatives
- Rewrite history now with `git filter-repo`: deferred. It is approved in principle as one
  pre-sharing task (rewrite locally, push to a new private repository, archive the old
  one) so that commit-by-commit history is kept and stale pull-request refs on the old
  repository are left behind.
- A third-party secret scanner (gitleaks): to be decided before anyone else gets access.
- Signed commits: not now.

## Consequences
- Every clone runs `uv run pre-commit install` once to get all three hooks.
- The CI python job checks out full history (`fetch-depth: 0`).
- Until the rewrite, `privacy-audit` lists the known legacy findings on every run.

## Sources
[Claude Code: memory files](https://code.claude.com/docs/en/memory) ·
[pre-commit: supported git hooks and `default_install_hook_types`](https://pre-commit.com/) ·
[GitHub: push event payload](https://docs.github.com/en/webhooks/webhook-events-and-payloads#push) ·
[actions/checkout `fetch-depth`](https://github.com/actions/checkout)
