# AI assistance

SepsiScope was developed with AI assistance from **Claude Code** (Anthropic), used as a
pair programmer: proposing plans, drafting code, tests and documentation, and checking
versions and sources.

All decisions were approved by me, and **every component was reviewed, tested and
understood by me** before being committed. Commits are authored by me alone; no AI
co-author trailer is used.

| Phase | Date | What the assistant did | How it was verified |
|---|---|---|---|
| Privacy hardening | 2026-10-22 | Read-only audit (tree, history, GitHub settings and logs), neutral rewording, `sepsiscope.audit` rules, git hooks, `privacy-audit` command, CI commit check, ADR 0016, tests | 203 tests pass three times, ruff, mypy, pre-commit and web build clean; `privacy-audit` and a full-history scan run twice; every new commit `+0000` |
| 1 — Data | 2026-10-10 | Downloader, fingerprint check, Parquet build, cleaning rules, schemas, splits, EDA code and figures, data card, vendored scorer, tests | Fingerprint matches on all 28 checks, 136 tests plus a real-data test, byte-identical rebuilds, schema validation, cleaning bounds checked against observed values (ADR 0014), critique log in the internal development notes |
| 0 — Foundation | 2026-10-10 | Inventory, environment setup, repo skeleton, tests, hooks, CI, docs | Tests run 3× green, pre-commit clean, privacy hook demo, link check, critique loop (see the Phase 0 report) |
