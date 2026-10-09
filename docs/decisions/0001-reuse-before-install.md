# 0001 — Reuse existing tools; install only what is missing

**Date:** 2026-10-10 · **Status:** Accepted

## Context
The local machine already hosts other projects that depend on the installed Python 3.13,
Node 26, git and gh. Upgrades or duplicate runtimes could break them and waste disk.

## Decision
A read-only inventory was taken first. Reused: the installed Python 3.13, Node 26
(satisfies Vite 8's `^20.19.0 || >=22.12.0`), npm, git and gh.
Installed with `brew install` only: **uv 0.12.24** and **libomp 23.1.3**. No `brew upgrade`,
no `brew cleanup`, no sudo. `node@24` was not installed.

## Alternatives
- uv-managed Python download: rejected, a duplicate interpreter is not needed.
- node@24: rejected, Node 26 already satisfies Vite's `engines`.
- uv via the `curl | sh` installer: rejected; Homebrew is the approved source.

## Consequences
The project shares Homebrew's Python; if `python@3.13` is upgraded later, run `uv sync`
to rebuild `.venv`. uv's package cache (`~/.cache/uv`) is shared across projects.

## Sources
[formulae.brew.sh/uv](https://formulae.brew.sh/formula/uv) ·
[formulae.brew.sh/libomp](https://formulae.brew.sh/formula/libomp) ·
[Vite on npm (engines)](https://www.npmjs.com/package/vite)
