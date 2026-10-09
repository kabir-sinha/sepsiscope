# SepsiScope

An explainable, alarm-budgeted early-warning system that predicts sepsis hours before
onset from routine ICU data, validated across two hospitals.

> **Research prototype — not for clinical use.** Not a medical device. It must not be
> used to make decisions about real patients.

## Setup

Prerequisites: Homebrew with `python@3.13`, `uv`, `libomp` and `node`.

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

Dev servers bind to `http://127.0.0.1`. If a browser's HTTPS-only mode blocks plain-HTTP
localhost, open the address in a normal window.

## Documentation

- [Evaluation protocol (frozen)](docs/protocol.md)
- [Privacy](docs/privacy.md) · [Operations](docs/ops.md) · [Decisions](docs/decisions/README.md)
- [Model card](docs/model_card.md) · [TRIPOD+AI](docs/tripod_ai.md)

## AI assistance

Development was AI-assisted using Claude Code (Anthropic). Every component was
reviewed, tested and understood by me. Details: [docs/ai_assistance.md](docs/ai_assistance.md).

## Data attribution

PhysioNet/CinC Challenge 2019 (Reyna et al., Critical Care Medicine 2020), CC BY 4.0.
<https://physionet.org/content/challenge-2019/1.0.0/>. The data is not included in this
repository.

## Licence

© 2026 Kabir Sinha. All rights reserved.

Third-party material in `third_party/` keeps its own licence.
