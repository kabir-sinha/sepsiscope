# 0017 — Security lockdown: patched toolchain, package fixes, gitleaks, sandbox, clean history

**Date:** 2026-11-13 · **Status:** Accepted · **Does not change** `docs/protocol.md`

## Context
Security advisories published after Phase 1 affected the toolchain (uv trusting a
compromised root certificate, CPython, Node and git security releases) and several
locked Python packages (pillow, mlflow, certifi, virtualenv and others). Server-side
secret scanning is not relied on for this repository, so secrets must be caught locally
and in CI. Older commits still held personal wording and local timezone offsets
(ADR 0016 recorded them as known).

## Decision
- **Toolchain minimums.** uv `>=0.13.4,<0.14` (`[tool.uv] required-version`), Python
  `>=3.13.18,<3.14` (`requires-python`), Node `>=26.13.1`. The project stays on Python 3.13
  even though uv 0.13 defaults to 3.15. CI prints the resolved versions and fails below
  these minimums. Local tools are upgraded one Homebrew formula at a time, without a
  global upgrade, cleanup or dependent upgrades.
- **Package fixes** come only from official releases, through `uv lock
  --upgrade-package` for the flagged packages (no unrelated upgrades). Dependabot pull
  requests are applied locally with `TZ=UTC` and then closed. `pip-audit` and `npm audit`
  must both report zero.
- **gitleaks.** A pre-commit hook runs the system binary on staged changes (redacted). A
  CI job downloads the official release at a pinned version and verifies both the tarball
  and the release's checksums file against SHA-256 values written in the workflow, then
  scans the full history. No third-party action is used.
- **Claude Code sandbox** (maintainer-applied user settings): Bash runs sandboxed and may
  not fall back to unsandboxed; network limited to the package registries, GitHub,
  PhysioNet and reference-lookup hosts; credential stores denied to both sandboxed
  commands and file tools; file tools refuse reads outside the working directories;
  bypass-permissions mode disabled; telemetry and error reporting off. Only `git push` and
  `git fetch` run outside the sandbox, because the git credential helper uses the OS
  keychain. Claude Code's own updates stay on.
- **Clean history.** The history is rewritten once, in a scratch clone outside the
  repository: the phrases `privacy-audit` lists as known (and the other wording neutralised
  on 2026-10-22) are replaced, and every commit date is kept at the same instant with a
  `+0000` offset. The HEAD tree must stay identical. The result goes to a **new** private
  repository; the old one is renamed `sepsiscope-legacy`, kept private, and deleted by the
  maintainer later. Afterwards `privacy-audit` is strict by default.

## Alternatives
- Rewriting the existing repository in place with a force-push: rejected; the hosting
  service keeps pull-request references to old commits.
- A third-party gitleaks action: rejected in favour of a pinned, checksum-verified binary.
- Disabling all non-essential Claude Code traffic: rejected, because it also stops Claude
  Code's own (security) updates.

## Consequences
- Every clone needs uv 0.13.4 or newer, Python 3.13.18 or newer and, for the web app,
  Node 26.13.1 or newer.
- gitleaks must be installed locally for the pre-commit hook.
- Commit hashes change once; documents that cite hashes are remapped with the rewrite's
  commit map, and CI run numbers before the rewrite refer to the legacy repository.

## Sources
[uv required-version](https://docs.astral.sh/uv/reference/settings/#required-version) ·
[astral-sh/setup-uv README](https://github.com/astral-sh/setup-uv) ·
[gitleaks releases](https://github.com/gitleaks/gitleaks/releases) ·
[git-filter-repo](https://github.com/newren/git-filter-repo) ·
[Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing) ·
[Claude Code settings](https://code.claude.com/docs/en/settings) ·
[Pillow 13.0.0 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
