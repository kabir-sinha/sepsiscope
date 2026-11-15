"""Byte-identical check: only git_commit in model.json may differ (ADR 0024 item 7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sepsiscope.repro import compare, digest, main, manifest

C1 = "a" * 40
C2 = "b" * 40


def _tree(root: Path, commit: str = C1, trees: int = 113) -> None:
    (root / "models" / "lgbm_A2B").mkdir(parents=True)
    info = {"num_trees": trees, "git_commit": commit, "lightgbm_version": "4.7.0"}
    (root / "models" / "lgbm_A2B" / "model.json").write_text(json.dumps(info, indent=1) + "\n")
    (root / "models" / "lgbm_A2B" / "model.txt").write_text("tree\n")
    (root / "reports" / "results").mkdir(parents=True)
    (root / "reports" / "results" / "lgbm_A2B.json").write_text('{"auroc": 0.8}\n')
    (root / "data" / "demo").mkdir(parents=True)
    (root / "data" / "demo" / "demo_B2A.json").write_text("{}\n")


def test_identical_outputs_pass(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    _tree(a)
    _tree(b)
    old = manifest(a)
    assert len(old) == 4
    assert compare(old, manifest(b)) == {"changed": [], "missing": [], "added": []}


def test_only_git_commit_is_ignored(tmp_path: Path) -> None:
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    _tree(a, commit=C1)
    _tree(b, commit=C2)
    _tree(c, commit=C1, trees=114)
    assert compare(manifest(a), manifest(b))["changed"] == []
    assert compare(manifest(a), manifest(c))["changed"] == ["models/lgbm_A2B/model.json"]


def test_other_files_count_every_byte(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    _tree(a)
    _tree(b)
    (b / "reports" / "results" / "lgbm_A2B.json").write_text('{"auroc": 0.80}\n')
    (b / "models" / "lgbm_A2B" / "extra.txt").write_text("x\n")
    (b / "data" / "demo" / "demo_B2A.json").unlink()
    diff = compare(manifest(a), manifest(b))
    assert diff == {
        "changed": ["reports/results/lgbm_A2B.json"],
        "missing": ["data/demo/demo_B2A.json"],
        "added": ["models/lgbm_A2B/extra.txt"],
    }


def test_git_commit_outside_model_json_counts(tmp_path: Path) -> None:
    p, q = tmp_path / "x.json", tmp_path / "y.json"
    p.write_text(f'{{"git_commit": "{C1}"}}\n')
    q.write_text(f'{{"git_commit": "{C2}"}}\n')
    assert digest(p) != digest(q)


def test_two_commit_fields_are_an_error(tmp_path: Path) -> None:
    p = tmp_path / "model.json"
    p.write_text(f'{{"git_commit": "{C1}", "x": {{"git_commit": "{C2}"}}}}\n')
    with pytest.raises(ValueError):
        digest(p)


def test_cli_write_then_compare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    m = tmp_path / "manifest.json"
    assert main(["--write", str(m)]) == 0
    assert main(["--compare", str(m)]) == 0
    (tmp_path / "models" / "lgbm_A2B" / "model.txt").write_text("other\n")
    assert main(["--compare", str(m)]) == 1
    assert main([]) == 2


def test_committed_manifest_is_not_an_output(tmp_path: Path) -> None:
    _tree(tmp_path)
    before = manifest(tmp_path)
    (tmp_path / "reports" / "manifest_c6.json").write_text("{}\n")
    (tmp_path / "reports" / "results" / "manifest_x.json").write_text("{}\n")  # not top level
    after = manifest(tmp_path)
    assert "reports/manifest_c6.json" not in after
    assert compare(before, after)["added"] == ["reports/results/manifest_x.json"]
