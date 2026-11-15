# 0025 — Attribution on the demo

**Date:** 2026-11-15 · **Status:** Accepted · **Narrows** ADR 0023 (one exception) ·
**Does not change** `docs/protocol.md`

## Context
ADR 0023 denies the maintainer's name in every tracked file. The maintainer asked for one
visible attribution on the demo page, so a reader of the demo can see who built it.

## Decision
- Exactly one attribution is allowed: the text `Built by` followed by the maintainer's
  **first name only**, as small, muted text under the title in the demo header
  (`web/src/App.tsx`). Nothing else may follow the first name on that line.
- The rules never contain the name. The commit guard, `privacy-audit`, `deep_scan.py` and
  `privacy_pass.sh` build the allowed text at run time as `Built by ` + the first word of
  the `allow-author-name:` line in the gitignored local denylist, and remove it **only** in
  `web/src/App.tsx`, case-sensitively and only as the whole text. Every other occurrence of
  the first name, the full name, the surname, a lower-case variant or the same text in any
  other file is still a finding.
- `tests/test_attribution.py` reads the first name from that one header line and fails if
  the name appears in any other tracked file, or more than once in that file. It needs no
  local file, so it also runs in CI.
- The full name stays banned in every tracked file; commit metadata is unchanged (ADR 0023).

## Consequences
- The demo shows who built it; the rest of the repository stays name-free.
- Moving the header to another file needs a new ADR and a change of `ATTRIBUTION_FILE` in
  `src/sepsiscope/audit/denylist.py` and `scripts/deep_scan.py`.
