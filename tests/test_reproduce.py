"""`sepsiscope reproduce`: step order, --retune, stop at the first failure (no real runs)."""

from __future__ import annotations

from sepsiscope import reproduce


def test_steps_in_order_without_tuning() -> None:
    s = reproduce.steps()
    names = [" ".join(a) for a in s]
    assert names[0] == "data verify"
    assert names.index("features build") < names.index("train --direction A2B --no-track")
    assert names.index("train --direction B2A --no-track") < names.index("evaluate --all-models")
    assert names[-1] == "demo build"
    assert not any(a[0] == "tune" for a in s)
    assert not any("download" in a for a in s)  # the only network step stays separate


def test_retune_adds_tuning_before_training() -> None:
    names = [" ".join(a) for a in reproduce.steps(retune=True)]
    assert names.index("tune --direction A2B") < names.index("train --direction A2B --no-track")


def test_run_stops_at_first_failure() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> int:
        calls.append(argv)
        return 3 if argv[1:] == ["data", "build"] else 0

    lines: list[str] = []
    code = reproduce.run(reproduce.steps(), runner, lines.append)
    assert code == 3
    assert [c[1:] for c in calls] == [["data", "verify"], ["data", "build"]]
    assert lines[-1] == "stopped: step 2 exited with 3"
    assert calls[0][0].endswith("sepsiscope")


def test_run_all_ok() -> None:
    lines: list[str] = []
    assert reproduce.run([("a",), ("b",)], lambda argv: 0, lines.append) == 0
    assert lines == ["[1/2] sepsiscope a", "[2/2] sepsiscope b", "all steps finished"]
