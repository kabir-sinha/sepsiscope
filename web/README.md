# SepsiScope demo (web)

React + TypeScript single-page demo, built with Vite. It shows the patient replay, the
explanations and the committed results, and talks only to the local demo API on
`127.0.0.1` (same origin).

```bash
npm ci && npm run lint && npm run build
```

Then serve it with the API from the repository root: `uv run sepsiscope demo serve`.
See the main [README](../README.md) for the project.
