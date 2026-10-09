# Handoff

State of the work, so anyone can pick it up from the repository alone.

## Phase 0 status: complete

- Repository `kabir-sinha/sepsiscope` is **private**; default branch `main`.
- First CI run is green: run `38003153138` (jobs `python` and `web`).
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
- [ ] **Task 3:** Node consistency: `web/.nvmrc` = 26 read by CI through
  `node-version-file`; check that the `@types/node` major matches the runtime; if
  consistent and CI passes, merge the `@types/node` 26 PR, otherwise stop and explain.
  _Not started._
- [ ] **Task 4:** pin `runs-on: ubuntu-24.04` in both CI jobs (verify the label in the
  runner-images docs) and note in `docs/ops.md` to upgrade deliberately later. _Not started._

When all four are done: push, record the CI result, and mark Phase 0 fully closed.

## Next after these

Phase 1 (data download + fingerprint check).
