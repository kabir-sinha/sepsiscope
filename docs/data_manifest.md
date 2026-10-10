# Data manifest (summary)

The dataset itself is never committed. This file records what was downloaded, so that
anyone can check that they have the same bytes.

| | |
|---|---|
| Source | Official PhysioNet public bucket, `https://physionet-open.s3.amazonaws.com/`, prefix `challenge-2019/1.0.0/training/` |
| Dataset | PhysioNet/CinC Challenge 2019 v1.0.0, training sets A and B (CC BY 4.0) |
| Downloaded | 2026-10-10, with `uv run sepsiscope data download` |
| Files | 40336 255057484 20336 20000 131388704 123668780 (`training_setA`: , `training_setB`: ) |
| Bytes |  (`training_setA`: , `training_setB`: ) |
| Integrity | every file: size equals the listed size, and MD5 equals the S3 ETag (all 40336 255057484 20336 20000 131388704 123668780 ETags are plain MD5s; none is multipart) |
| Manifest | `data/raw/MANIFEST.json` (key, size, md5 per file; git-ignored) |
| SHA-256 of the manifest | `13792ab7d150b76354c80aa554b295b77bc63990aa0544bfbcfb8a0cf8910998` |

## How to reproduce

```bash
uv run sepsiscope data download
```

```bash
shasum -a 256 data/raw/MANIFEST.json
```

```bash
uv run sepsiscope data verify
```

The download is resumable: every run lists the bucket again and re-checks the size and
MD5 of every file. The manifest is written with sorted keys, so the same listing always
gives the same SHA-256. `data verify` then recomputes the dataset fingerprint frozen in
`docs/protocol.md` (28 checks) and fails on any mismatch.

PhysioNet's own `SHA256SUMS.txt` for this dataset covers only three top-level files, not
the patient files, so the S3 MD5 ETag is the strongest per-file check available.
