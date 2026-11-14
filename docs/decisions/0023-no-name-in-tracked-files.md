# 0023 — No personal name in tracked files

**Date:** 2026-11-14 · **Status:** Accepted · **Supersedes** the name policy of ADR 0016 ·
**Does not change** `docs/protocol.md`

## Context
ADR 0016 allowed the maintainer's name in two places: the README copyright line and the
`pyproject.toml` author field. The final privacy scan before the Milestone 4 push asked for
no personal name anywhere in the tracked files.

## Decision
- The README notice reads `© 2026 SepsiScope contributors. All rights reserved.` and the
  `pyproject.toml` author is `SepsiScope contributors` with the noreply address. The project
  stays all rights reserved (ADR 0003); "SepsiScope contributors" is a common way to name
  the holders of a project's copyright, and the git history records who wrote what.
- The privacy rules deny the name on **every** line of every tracked file, and the commit
  guard does the same for staged files.
- History is **not** rewritten. Blobs that exist only in commits before 2026-11-15 keep the
  old allowance (only the exact copyright and author line shapes), so `privacy-audit`
  stays strict without a rewrite.
- **Commit names.** The 28 commits not yet on GitHub were rewritten locally (dates kept,
  `+0000`) so that their author and committer name is the maintainer's first name and no
  old README/pyproject version in them carries the full name; commits already on GitHub
  (up to `31bb0c5`) are untouched. The audit rejects any commit name that contains a
  denylist value unless it is exactly the one name declared in the gitignored local file
  (`allow-author-name:`), so that name is never written into a tracked file. CI has no
  local file and checks emails and offsets only.

## Consequences
- Anyone reading the files at HEAD sees no personal name.
- A later name on any line, the copyright line included, fails the commit guard and the
  audit.
