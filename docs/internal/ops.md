# Operations

## Repository state (2026-10-10)

| Item | State |
|---|---|
| Repository | The maintainer's `sepsiscope`, default branch `main`; private during development, prepared for public release as `v1.1.0` (visibility is changed by the maintainer) |
| Created with | `gh repo create --private --source=. --remote=origin --push --disable-wiki` |
| Features | Issues on; Wiki, Projects and Discussions off; delete head branch on merge on |
| Auth method | GitHub CLI `gh` OAuth token in gh's credential store (details below); no PAT created |
| Dependabot alerts | **Enabled** (`PUT /repos/{owner}/{repo}/vulnerability-alerts` accepted) |
| Dependabot security updates | **Enabled** (`GET .../automated-security-fixes` returned `enabled: true`) |
| Dependabot version updates | `uv`, `npm` and `github-actions`, weekly; major updates of `typescript` and `@types/node` are ignored on purpose |
| PR #1 (TypeScript 7.0.2) | **Closed** with `@dependabot ignore this major version`; the project stays on TypeScript ~6.0 |
| PR #2 (`@types/node` 26.6.4) | **Merged** as `3c3cb0b`, so the types match the Node 26 runtime in `web/.nvmrc` |
| Open pull requests | None |
| CI runner | Both jobs pinned to `ubuntu-24.04` (see the CI runner note) |
| Latest green CI run | `38004754410` on `a39e37a` (jobs `python` and `web`); newer runs are in the Actions tab |
| Watching | All Activity (`subscribed: true`, `ignored: false`) |
| Collaborators | Only the maintainer (admin) |
| Branch protection | **Pending**; rules below, to apply when enabled |

Commit history: every commit is authored by the project's GitHub noreply address, except
the merged Dependabot PR `3c3cb0b`, whose author is `dependabot[bot]` (GitHub's bot
identity, not personal data).

Pre-push check: the full history was scanned three ways (git grep over every commit, every
blob object, and a fresh clone including image metadata) for the local username, home
path, hostname, non-noreply emails, IP/MAC addresses, UUIDs, tokens and keys. Clean.

## Authentication to GitHub

- **Method:** the GitHub CLI `gh`, with its token kept in **gh's credential store**.
  Git uses it over HTTPS. No new tool or token was created for this project.
- **Token expiry:** `gh auth login` OAuth tokens do not have a fixed expiry date; they stay
  valid until revoked at <https://github.com/settings/applications>. Expiry date to record:
  **none (OAuth app token)**. GitHub automatically revokes OAuth tokens that go unused for a year
  ([token expiration and revocation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/token-expiration-and-revocation)). Check with `gh auth status` before each push session.
- Docs: [gh auth login](https://cli.github.com/manual/gh_auth_login).

## gh telemetry

`gh config get telemetry` was `enabled`; set to **`disabled`** on 2026-10-10 with
`gh config set telemetry disabled` (global gh setting, approved by the maintainer).

## Branch protection for `main`

Reference: [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

**Status:** _pending; rules below, to apply when enabled._ Apply these rules then
(Settings → Branches → Add classic branch protection rule, or Settings → Rules → Rulesets):

- Branch name pattern: `main`
- Require a pull request before merging (0 required approvals)
- Require status checks to pass: `python`, `web` (exact names confirmed from the first CI run); require branches to be up to date
- Do not allow force pushes
- Do not allow deletions
- Leave "Do not allow bypassing the above settings" **unchecked**, so the admin (the maintainer) can still bypass when needed

## Dependabot

- `.github/dependabot.yml`: weekly version updates for `uv` (root), `npm` (`web/`) and
  `github-actions` (SHA-pinned workflow actions)
  ([options reference](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference)).
- Dependabot alerts and security updates: **enabled** on 2026-10-10 through the REST API.

## CI runner note

Both CI jobs are pinned to `runs-on: ubuntu-24.04` (label confirmed in the
[runner-images README](https://github.com/actions/runner-images#available-images)), because
GitHub announced that `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19. **Upgrade
deliberately later:** change the label to `ubuntu-26.04` in a pull request, let CI prove it,
then merge. Dependabot does not update runner labels.

## Release and visibility checklist (going public later)

1. `uv run pre-commit run --all-files` is clean.
2. `git log --format='%ae %ce' | sort -u` shows only the noreply address, and
   `uv run sepsiscope privacy-audit` (strict by default) passes.
3. `git grep -nI -e "$HOME" -e "$(whoami)"` finds nothing; no data, models or `mlruns/` are tracked (`git ls-files`).
4. The README disclaimer, licence notice and data attribution are present.
5. `third_party/` has each vendored file's own licence.
6. Settings → General → Danger Zone → Change visibility → Public.
7. Immediately apply the branch protection rules above.
8. Turn on secret scanning and push protection (free for public repos).
9. Confirm Dependabot alerts are on.
