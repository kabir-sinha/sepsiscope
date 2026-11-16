# SepsiScope

An explainable, alarm-budgeted early-warning system that predicts sepsis hours before
onset from routine ICU data, validated across two hospitals.

> **Research prototype — not for clinical use.** Not a medical device. It must not be
> used to make decisions about real patients.

## Setup

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/) 0.12 and Node 26.
**macOS:** LightGBM also needs the OpenMP runtime `libomp` (for example `brew install libomp`).

```bash
git clone https://github.com/kabir-sinha/sepsiscope.git && cd sepsiscope
```

```bash
uv sync --locked --all-extras
```

```bash
uv run pre-commit install
```

```bash
uv run sepsiscope doctor
```

```bash
cd web && npm ci && npm run build
```

Run the checks: `uv run pytest`, `uv run ruff check .`, `uv run mypy src`.

## Reproduce every result

Download the data once (about 320 MB, into the git-ignored `data/` folder; the only step
that uses the network):

```bash
uv run sepsiscope data download
```

Then one command runs everything else in order (data verify, build and splits, features,
training from the committed tuned parameters, evaluation, ablations, the exploratory
model, the Batch C analyses and the demo data) and stops at the first failure:

```bash
uv run sepsiscope reproduce
```

About 30 minutes and up to about 6 GiB of memory on a laptop. `--dry-run` lists the steps;
`--retune` repeats the hyperparameter tuning first (about 30 minutes more; a resumed tuning
run is not byte-identical). To check that a re-run gives the same files:

```bash
uv run python scripts/byte_check.py --write /tmp/before.json
```

and after the re-run `uv run python scripts/byte_check.py --compare /tmp/before.json`
(only the commit hash inside each `model.json` is ignored). The committed
`reports/manifest_c6.json` holds the reference hashes of the Batch C gate (paths and
SHA-256 only): `uv run python scripts/byte_check.py --compare reports/manifest_c6.json`.

Dev servers bind to `http://127.0.0.1`. If a browser's HTTPS-only mode blocks plain-HTTP
localhost, open the address in a normal window.

## Documentation

- [Evaluation protocol (frozen)](docs/protocol.md)
- [Data card](docs/data_card.md) · [EDA findings](docs/eda_findings.md) · [Data manifest](docs/data_manifest.md)
- [Privacy](docs/privacy.md) · [Operations](docs/internal/ops.md) · [Decisions](docs/decisions/README.md)
- [Model card](docs/model_card.md) · [Datasheet](docs/datasheet.md) · [TRIPOD+AI](docs/tripod_ai.md) · [Changelog](CHANGELOG.md)

## AI assistance

Development was AI-assisted using Claude Code (Anthropic). Every component was
reviewed, tested and understood by me. Details: [docs/ai_assistance.md](docs/ai_assistance.md).

## Data attribution

PhysioNet/CinC Challenge 2019 (Reyna et al., Critical Care Medicine 2020), CC BY 4.0.
<https://physionet.org/content/challenge-2019/1.0.0/>. The data is not included in this
repository.

## Licence

© 2026 SepsiScope contributors. All rights reserved.

Third-party material in `third_party/` keeps its own licence.
