"""Optuna tuning of the LightGBM model, exactly per ADR 0021 (plan B2).

- TPE sampler (seed 42), median pruner, at most 50 finished trials, ``n_jobs=1``.
- Objective: mean row-level AUPRC over ``GroupKFold(5)`` (grouped by patient) on the
  source hospital's **training split only**. Each fold stops early on its own held-out
  part (2,000-round cap). The running mean is reported to the pruner after every fold.
- Resumable: trials live in an Optuna journal file in the ignored ``mlruns/`` folder; the
  same command continues where it stopped. TPE's internal random state restarts on
  resume, so a resumed run is not byte-identical to an uninterrupted one.
- 6-hour guard: from the 5th finished trial on, after every trial, the remaining time is
  projected from the measured fold-fit times. Over the budget, a status JSON is written,
  the study stops after the current trial (every journal write is already on disk) and
  the command exits with ``GUARD_EXIT_CODE``. Nothing ever waits for input.

Tracked output (``reports/tuning/lgbm_{direction}.json``) holds numbers only: parameters,
fold AUPRCs, rounds and trial states; no times, paths or patient IDs.
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import optuna
from optuna.storages import JournalStorage
from optuna.storages.journal import JournalFileBackend
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold

from sepsiscope.data.io import LABEL
from sepsiscope.evaluation.run import DIRECTIONS
from sepsiscope.features.causal import KEYS
from sepsiscope.features.pipeline import read_features
from sepsiscope.logscrub import ScrubFilter
from sepsiscope.models import lgbm
from sepsiscope.models.pipeline import train_ids

N_TRIALS = 50
N_FOLDS = 5
SEED = 42
GUARD_AFTER = 5
BUDGET_HOURS = 6.0
GUARD_EXIT_CODE = 3
STORE_SUBDIR = Path("tuning")  # inside mlruns/ (ignored, blocked by the privacy guard)
FINISHED = (optuna.trial.TrialState.COMPLETE, optuna.trial.TrialState.PRUNED)

log = logging.getLogger("sepsiscope.tuning")


def search_space(trial: optuna.Trial) -> dict[str, Any]:
    """Fixed before running (plan B2)."""
    return {
        "num_leaves": trial.suggest_int("num_leaves", 15, 255, log=True),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 500, log=True),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "bagging_freq": 1,
        "lambda_l1": trial.suggest_float("lambda_l1", 1e-3, 10.0, log=True),
        "lambda_l2": trial.suggest_float("lambda_l2", 1e-3, 10.0, log=True),
    }


@dataclass
class TuneData:
    x: np.ndarray
    y: np.ndarray
    folds: list[tuple[np.ndarray, np.ndarray]]
    features: list[str]


def prepare(frame: Any, features: list[str]) -> TuneData:
    """Matrix, labels and patient-grouped folds of the training rows given."""
    x = lgbm.matrix(frame, features)
    y = frame[LABEL].to_numpy().astype(np.int8)
    groups = frame["pid"].to_numpy()
    folds = [(tr, va) for tr, va in GroupKFold(n_splits=N_FOLDS).split(x, y, groups)]
    return TuneData(x, y, folds, features)


def make_objective(
    data: TuneData, seed: int, clock: Callable[[], float]
) -> Callable[[optuna.Trial], float]:
    def objective(trial: optuna.Trial) -> float:
        params = lgbm.make_params(search_space(trial), seed)
        scores: list[float] = []
        rounds: list[int] = []
        seconds: list[float] = []
        for k, (tr, va) in enumerate(data.folds):
            start = clock()
            booster = lgbm.fit(
                data.x[tr], data.y[tr], params, lgbm.MAX_ROUNDS, (data.x[va], data.y[va])
            )
            pred = booster.predict(data.x[va], num_iteration=booster.best_iteration)
            seconds.append(clock() - start)
            scores.append(float(average_precision_score(data.y[va], pred)))
            rounds.append(int(booster.best_iteration))
            trial.set_user_attr("fold_auprc", scores)
            trial.set_user_attr("fold_rounds", rounds)
            trial.set_user_attr("fold_seconds", seconds)
            trial.report(float(np.mean(scores)), k)
            if trial.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(scores))

    return objective


def finished(study: optuna.Study) -> list[optuna.trial.FrozenTrial]:
    return [t for t in study.get_trials(deepcopy=False) if t.state in FINISHED]


def projection_hours(study: optuna.Study, n_trials: int) -> float:
    """Remaining hours = trials left x folds per trial x seconds per fold (all measured)."""
    done = finished(study)
    fold_seconds = [s for t in done for s in t.user_attrs.get("fold_seconds", [])]
    if not done or not fold_seconds:
        return 0.0
    folds_per_trial = len(fold_seconds) / len(done)
    remaining = max(0, n_trials - len(done))
    return remaining * folds_per_trial * statistics.fmean(fold_seconds) / 3600.0


class Guard:
    """Optuna callback: stops the study when the projection exceeds the budget."""

    def __init__(self, n_trials: int, after: int, budget_hours: float) -> None:
        self.n_trials, self.after, self.budget = n_trials, after, budget_hours
        self.tripped = False
        self.projection = 0.0

    def __call__(self, study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        done = len(finished(study))
        log.info(
            "trial %d %s value=%s finished=%d", trial.number, trial.state.name, trial.value, done
        )
        if done >= self.n_trials:
            study.stop()
            return
        if done >= self.after:
            self.projection = projection_hours(study, self.n_trials)
            if self.projection > self.budget:
                self.tripped = True
                log.warning(
                    "guard: projected %.2f h remaining > %.1f h", self.projection, self.budget
                )
                study.stop()


@dataclass(frozen=True)
class TuneOutcome:
    direction: str
    state: str  # "finished" or "guard_exit"
    completed_trials: int
    resumed: bool
    best_value: float | None
    best_params: dict[str, Any] | None
    median_rounds: int | None
    status_path: Path
    result_path: Path | None


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


def result_document(study: optuna.Study, direction: str, resumed: bool) -> dict[str, Any]:
    done = finished(study)
    best = study.best_trial
    return {
        "direction": direction,
        "adr": "0021",
        "sampler": "TPE",
        "seed": SEED,
        "pruner": "median",
        "objective": f"mean row-level AUPRC over GroupKFold({N_FOLDS}), source training split",
        "max_trials": N_TRIALS,
        "round_cap": lgbm.MAX_ROUNDS,
        "early_stopping_rounds": lgbm.EARLY_STOPPING_ROUNDS,
        "completed_trials": len(done),
        "pruned_trials": sum(t.state == optuna.trial.TrialState.PRUNED for t in done),
        "resumed": resumed,
        "best": {
            "trial": best.number,
            "mean_auprc": best.value,
            "params": best.params,
            "fold_auprc": best.user_attrs["fold_auprc"],
            "fold_rounds": best.user_attrs["fold_rounds"],
            "median_rounds": int(statistics.median(best.user_attrs["fold_rounds"])),
        },
        "trials": [
            {
                "number": t.number,
                "state": t.state.name,
                "params": t.params,
                "fold_auprc": t.user_attrs.get("fold_auprc", []),
                "fold_rounds": t.user_attrs.get("fold_rounds", []),
                "mean_auprc": t.value,
            }
            for t in done
        ],
    }


def tune(
    data: TuneData,
    direction: str,
    store_dir: Path,
    result_path: Path,
    n_trials: int = N_TRIALS,
    guard_after: int = GUARD_AFTER,
    budget_hours: float = BUDGET_HOURS,
    clock: Callable[[], float] = time.perf_counter,
) -> TuneOutcome:
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    store_dir.mkdir(parents=True, exist_ok=True)
    storage = JournalStorage(JournalFileBackend(str(store_dir / f"lgbm_{direction}.journal")))
    study = optuna.create_study(
        study_name=f"lgbm_{direction}",
        storage=storage,
        sampler=optuna.samplers.TPESampler(seed=SEED),
        pruner=optuna.pruners.MedianPruner(),
        direction="maximize",
        load_if_exists=True,
    )
    already = len(finished(study))
    resumed = already > 0
    guard = Guard(n_trials, guard_after, budget_hours)
    start = clock()
    if already < n_trials:
        study.optimize(
            make_objective(data, SEED, clock),
            n_trials=n_trials - already,
            n_jobs=1,
            callbacks=[guard],
            gc_after_trial=True,
        )
    done = len(finished(study))
    status_path = store_dir / f"status_{direction}.json"
    status: dict[str, Any] = {
        "direction": direction,
        "state": "guard_exit" if guard.tripped else "finished",
        "completed_trials": done,
        "resumed": resumed,
        "elapsed_hours_this_run": (clock() - start) / 3600.0,
        "projected_remaining_hours": guard.projection,
        "budget_hours": budget_hours,
    }
    _write_json(status_path, status)
    if guard.tripped:
        return TuneOutcome(
            direction, "guard_exit", done, resumed, None, None, None, status_path, None
        )
    doc = result_document(study, direction, resumed)
    _write_json(result_path, doc)
    best = doc["best"]
    return TuneOutcome(
        direction,
        "finished",
        done,
        resumed,
        best["mean_auprc"],
        best["params"],
        best["median_rounds"],
        status_path,
        result_path,
    )


def final_tunable(best_params: dict[str, Any]) -> dict[str, Any]:
    """Best sampled parameters plus the fixed ones from the search space."""
    return {**best_params, "bagging_freq": 1}


def tuned_settings(result_path: Path) -> tuple[dict[str, Any], int] | None:
    """(tunable parameters, rounds) from a committed tuning result, if it exists."""
    if not result_path.is_file():
        return None
    best = json.loads(result_path.read_text(encoding="utf-8"))["best"]
    return final_tunable(best["params"]), int(best["median_rounds"])


def add_log_file(path: Path) -> logging.Handler:
    """Tuning log in the ignored store folder, with personal paths scrubbed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    handler.addFilter(ScrubFilter())
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    return handler


def load_training(direction: str, data_dir: Path, splits_dir: Path) -> TuneData:
    """Source hospital, training split only (no validation, calibration or target rows)."""
    source, _ = DIRECTIONS[direction]
    frame = read_features(data_dir, source)
    train = frame[frame["pid"].isin(train_ids(splits_dir, source))].reset_index(drop=True)
    del frame
    return prepare(train, [c for c in train.columns if c not in KEYS])
