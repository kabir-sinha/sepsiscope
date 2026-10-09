# 0010 — Vite react-ts template, pins untouched

**Date:** 2026-10-10 · **Status:** Accepted

## Context
A frontend skeleton is needed now; the real UI comes later.

## Decision
`npm create vite@9.2.1 web -- --template react-ts --no-interactive --no-immediate`
(9.2.1 was `latest` on 2026-10-10). The template's version ranges are kept exactly
(TypeScript `~6.0.2`, not 7). `package-lock.json` resolved React **19.3.0**, because the
template's `^19.2.8` allows minor updates. The only additions are a
"Research prototype — not for clinical use" banner, binding the dev/preview servers to
`127.0.0.1`, and `web/.nvmrc` = `26` for CI. npm 11's install-script protection was left
on: `fsevents` (optional, macOS file watching) did not run its install script, and the
build works.

## Alternatives
Tightening React to `~19.2.8`: offered, not chosen. Next.js: has its own telemetry and
is more than needed.

## Consequences
The npm lockfile pins exact versions and integrity hashes; `npm ci` reproduces it.

## Sources
[create-vite on npm](https://www.npmjs.com/package/create-vite) ·
[Vite: server.host](https://vite.dev/config/server-options.html#server-host)
