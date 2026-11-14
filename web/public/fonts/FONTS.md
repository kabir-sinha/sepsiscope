# Self-hosted fonts

IBM Plex, licensed under the SIL Open Font License 1.1 (`OFL-LICENSE.txt`, identical in
both packages). Served from this origin only; never loaded from a CDN.

Obtained 2026-11-14 with `npm pack` from the npm registry (not installed, not in
`package.json`). The `@ibm` scope can only be published by members of IBM's npm
organisation; each tarball's SHA-512 was checked against the registry's integrity value,
and both carry a registry signature. Only the Latin-1 subsets (`fonts/split/woff2/*-Latin1`)
are copied; characters outside them fall back to the system font.

| File | Source | Path in package | Bytes | SHA-256 |
|---|---|---|---|---|
| `IBMPlexSans-Regular-Latin1.woff2` | `@ibm/plex-sans@1.1.0` | `fonts/split/woff2/` | 20,984 | `b5ad7bd39f996144915f0ad9849a90183b27d8c28ad97ed98af5b1bebc51f6b1` |
| `IBMPlexSans-SemiBold-Latin1.woff2` | `@ibm/plex-sans@1.1.0` | `fonts/split/woff2/` | 22,260 | `fff0ab3a88b0b4aa0b693e4f0201359a15183b08e3fa5696d1918d8f0ade8ad5` |
| `IBMPlexSans-Bold-Latin1.woff2` | `@ibm/plex-sans@1.1.0` | `fonts/split/woff2/` | 21,256 | `914f1400f363e636b6f9cc7965aa807ff01e93586e1437617525cba0a62aa78d` |
| `IBMPlexMono-Regular-Latin1.woff2` | `@ibm/plex-mono@2.5.0` | `fonts/split/woff2/` | 17,544 | `e8993d946649b9d01abb1ed06d574b19d8ea3e66b5c3948602db335c44c18e56` |
| `OFL-LICENSE.txt` | `@ibm/plex-sans@1.1.0` | `LICENSE.txt` | 4,456 | `7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da` |

Tarball integrity (npm, SHA-512):

- `@ibm/plex-sans@1.1.0`: `sha512-WPgvO6Yfj2w5YbhyAr1tv95RUz4LRJlqN+CmYvBglabXteufP1D1E9BABMde+ZIKdRbFJDoKF5eQzfhpnbgZcQ==`
- `@ibm/plex-mono@2.5.0`: `sha512-STBJIPxPomOYPmBMO7z5TKPJUotAF9u3gAUumTqVgwgrAO+K4FRNh0MlhsoJjKhJKsMbBJR10/bk4inkj/wc1w==`

Check: `cd web/public/fonts && shasum -a 256 *.woff2 OFL-LICENSE.txt`
