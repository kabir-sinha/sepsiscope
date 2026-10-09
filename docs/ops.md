# Operations

## Authentication to GitHub

- **Method:** the GitHub CLI `gh`, already installed and signed in as `kabir-sinha`, with
  its token kept in **gh's credential store** (`gh auth status` shows where). Git uses it
  over HTTPS. No new tool or token was created for this project.
- **Token expiry:** `gh auth login` OAuth tokens do not have a fixed expiry date; they stay
  valid until revoked at <https://github.com/settings/applications>. Expiry date to record:
  **none (OAuth app token)**. GitHub automatically revokes OAuth tokens that go unused for a year
  ([token expiration and revocation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/token-expiration-and-revocation)). Check with `gh auth status` before each push session.
- **Fallback, only if `gh` stops working:** a fine-grained personal access token
  limited to *only* `kabir-sinha/sepsiscope`, with Contents R/W, Pull requests R/W,
  Workflows R/W and Metadata R, and a 90-day expiry, stored by git's credential
  helper. Record **only** the expiry date here, never the token:
  - Fine-grained PAT expiry: _n/a (not created)_
- Docs: [fine-grained PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens),
  [gh auth login](https://cli.github.com/manual/gh_auth_login).

## gh telemetry

`gh config get telemetry` was `enabled`; set to **`disabled`** on 2026-10-10 with
`gh config set telemetry disabled` (global gh setting, approved by the maintainer).

## Branch protection for `main`

Reference: [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

**Status:** _pending until the repo is public or Pro is active._ Apply these rules then
(Settings → Branches → Add classic branch protection rule, or Settings → Rules → Rulesets):

- Branch name pattern: `main`
- Require a pull request before merging (0 required approvals)
- Require status checks to pass: `python`, `web` (the CI job names); require branches to be up to date
- Do not allow force pushes
- Do not allow deletions
- Leave "Do not allow bypassing the above settings" **unchecked**, so the admin (the maintainer) can still bypass when needed

`.github/CODEOWNERS` already assigns every file to `@kabir-sinha`.

## Dependabot

- `.github/dependabot.yml`: weekly version updates for `uv` (root), `npm` (`web/`) and
  `github-actions` (SHA-pinned workflow actions)
  ([options reference](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference)).
- Dependabot alerts and the dependency graph: _status to record after checking
  Settings → Advanced Security (Code security) on github.com._

## Release and visibility checklist (going public later)

1. `uv run pre-commit run --all-files` is clean.
2. `git log --format='%ae %ce' | sort -u` shows only the noreply address.
3. `git grep -nI -e "$HOME" -e "$(whoami)"` finds nothing; no data, models or `mlruns/` are tracked (`git ls-files`).
4. The README disclaimer, licence notice and data attribution are present.
5. `third_party/` has each vendored file's own licence.
6. Settings → General → Danger Zone → Change visibility → Public.
7. Immediately apply the branch protection rules above.
8. Turn on secret scanning and push protection (free for public repos).
9. Confirm Dependabot alerts are on.
