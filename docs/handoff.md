# Handoff

State of the work, so anyone can pick it up from the repository alone.

## Phase 0 fully closed, ready for Phase 1

- Repository `kabir-sinha/sepsiscope` is **private**; default branch `main`.
- First CI run is green: run `38003153138` (jobs `python` and `web`). After the four
  follow-up tasks, CI is green on `df74bd2`: run `38004614423`, on `ubuntu-24.04`.
- Commit `1e7b118` (`docs(ops): record repository state after first push`) is
  pushed.
- Branch protection: pending; rules in `docs/ops.md`, to apply when enabled.

## Rules for this work

- Show diffs before committing.
- Verify every flag, option and label against official docs first.
- Never push without a clean privacy scan (username, home path, non-noreply emails).
- Never leave a half-applied change; stop only at a clean commit and record where.

## Pending tasks

- [x] **Task 1:** pushed `1e7b118` and `bceb8db` after a clean privacy scan.
- [x] **Task 2:** `ignore` rule for `typescript` semver-major updates added and pushed
  (`ba3152f`); PR #1 answered with `@dependabot ignore this major version`.
- [x] **Task 3:** runtime is Node 26 (`web/.nvmrc`, read by CI via `node-version-file`);
  `@types/node` moved from major 24 to 26.6.4 by merging PR #2 (`56a5bdb`, authored by
  `dependabot[bot]`); local `npm ci`, lint and build pass.
- [x] **Task 4:** both CI jobs pinned to `runs-on: ubuntu-24.04` (26e9efe); upgrade note in
  `docs/ops.md`.

All four are done and pushed. Open pull requests: none (#1 closed, #2 merged).

## Next after these

Phase 1 (data download + fingerprint check).
