"""Config loads safely, and bad configs fail loudly."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sepsiscope.config import DEFAULT_CONFIG, load_config


def _write(tmp_path: Path, data: object) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def _default() -> dict[str, object]:
    raw = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def test_default_config_loads() -> None:
    cfg = load_config()
    assert cfg.seed == 42
    assert cfg.alarm_budget == 0.05
    assert cfg.label_horizon_hours == 6
    assert cfg.features.icu_time is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("seed",), "42"),  # strict: no string->int coercion
        (("alarm_budget",), 0.0),
        (("alarm_budget",), 1.5),
        (("label_horizon_hours",), 0),
        (("paths", "data_dir"), "/" + "Users/someone/data"),
        (("paths", "data_dir"), "~/data"),
        (("paths", "data_dir"), "/etc"),
        (("paths", "data_dir"), "../outside"),
        (("paths", "data_dir"), "C:\\data"),
        (("features", "vitals"), "yes"),
    ],
)
def test_bad_values_fail(tmp_path: Path, path: tuple[str, ...], value: object) -> None:
    raw = _default()
    node: dict[str, object] = raw
    for key in path[:-1]:
        child = node[key]
        assert isinstance(child, dict)
        node = child
    node[path[-1]] = value
    with pytest.raises(ValidationError):
        load_config(_write(tmp_path, raw))


def test_unknown_key_fails(tmp_path: Path) -> None:
    raw = _default()
    raw["alarm_budgte"] = 0.1  # typo must not be silently ignored
    with pytest.raises(ValidationError):
        load_config(_write(tmp_path, raw))


def test_missing_key_fails(tmp_path: Path) -> None:
    raw = _default()
    del raw["seed"]
    with pytest.raises(ValidationError):
        load_config(_write(tmp_path, raw))


def test_non_mapping_root_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mapping"):
        load_config(_write(tmp_path, [1, 2, 3]))


def test_unsafe_yaml_tag_rejected(tmp_path: Path) -> None:
    p = tmp_path / "evil.yaml"
    p.write_text("!!python/object/apply:os.system ['echo pwned']\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        load_config(p)
