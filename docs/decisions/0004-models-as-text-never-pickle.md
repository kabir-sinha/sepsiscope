# 0004 — Models as LightGBM text + JSON; never pickle or joblib

**Date:** 2026-10-10 · **Status:** Accepted

## Context
Unpickling runs arbitrary code, so a tampered model file could execute commands. YAML
has the same risk with `yaml.load`.

## Decision
Models are saved with `Booster.save_model()` (text) plus `feature_schema.json` and are
loaded with `lightgbm.Booster(model_file=...)`. Configs are read with `yaml.safe_load`.
`pickle`, `joblib.load` and `yaml.load` are never used. The smoke test proves the text
round-trip gives identical predictions, and a config test proves a `!!python/object`
tag is rejected.

## Alternatives
joblib/pickle: rejected (code execution on load). ONNX: unnecessary for now.

## Consequences
Text models are human-readable, can be diffed, and are safe to load.

## Sources
[Python pickle security warning](https://docs.python.org/3/library/pickle.html) ·
[PyYAML safe_load](https://pyyaml.org/wiki/PyYAMLDocumentation) ·
[LightGBM Booster.save_model](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.Booster.html)
