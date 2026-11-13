"""`sepsiscope evaluate`: baselines under strict external validation (protocol, ADR 0019).

For a direction such as A2B (source A, target B):

1. Fit what needs fitting on the source hospital's **train** split only (logistic
   regression; NEWS2-as-probability).
2. Choose the alert threshold on the source **validation** split (alarm budget, tie-safe).
3. **Headline (strict):** apply that threshold to every target patient and report the
   protocol metrics with patient-level bootstrap 95 % CIs.
4. **Secondary, "deployment adaptation":** re-set the threshold from the target's
   unlabelled **calibration-split** scores and evaluate on the other target patients.

Result files hold numbers only: no patient IDs, no paths, no timestamps, so a re-run gives
byte-identical files.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from sepsiscope.config import Config
from sepsiscope.data.io import LABEL
from sepsiscope.data.splits import read_split
from sepsiscope.evaluation import metrics as m
from sepsiscope.features.causal import KEYS, schema_document
from sepsiscope.features.pipeline import read_features
from sepsiscope.models import baselines as b

MODELS: tuple[str, ...] = ("news2", "sirs", "qsofa", "lr")
DIRECTIONS: dict[str, tuple[str, str]] = {"A2B": ("A", "B"), "B2A": ("B", "A")}
RESAMPLES = 1000
DCA_THRESHOLDS = np.round(np.arange(0.0, 0.2001, 0.01), 2)
MODEL_LABELS: dict[str, str] = {
    "news2": "modified NEWS2 (max 17)",
    "sirs": "SIRS (max 4)",
    "qsofa": "modified qSOFA (max 2)",
    "lr": "logistic regression",
}
PROBABILITY_MODELS = ("lr", "news2")  # models with a probability for ECE / decision curves


@dataclass
class Cohort:
    """One hospital's rows, in patient order, with the derived index arrays."""

    frame: pd.DataFrame
    labels: np.ndarray
    patient: np.ndarray
    n_patients: int

    @classmethod
    def of(cls, frame: pd.DataFrame) -> Cohort:
        frame = frame.reset_index(drop=True)
        patient = m.patient_index(frame["pid"].to_numpy())
        n = int(patient[-1]) + 1 if len(patient) else 0
        return cls(frame, frame[LABEL].to_numpy().astype(np.int64), patient, n)

    def subset(self, pids: set[str]) -> Cohort:
        return Cohort.of(self.frame[self.frame["pid"].isin(pids)])


def _split_pids(splits_dir: Path, hospital: str) -> dict[str, set[str]]:
    doc = read_split(splits_dir / f"hospital_{hospital}.json")
    out: dict[str, set[str]] = {}
    for part in ("train", "val", "calibration"):
        ids = doc[part]
        assert isinstance(ids, list)
        out[part] = {str(x) for x in ids}
    return out


@dataclass(frozen=True)
class Scorer:
    """A fitted model: ``score`` ranks hours, ``probability`` (if any) is calibrated-ish."""

    name: str
    score: Callable[[pd.DataFrame], np.ndarray]
    probability: Callable[[pd.DataFrame], np.ndarray] | None
    fitted: Mapping[str, object]


def fit_scorer(model: str, train: pd.DataFrame, features: list[str], seed: int) -> Scorer:
    if model == "lr":
        _, js = b.fit_logistic(train, features, LABEL, seed)
        return Scorer("lr", js.predict_proba, js.predict_proba, {"logistic": asdict(js)})
    rule = b.RULE_SCORES[model]
    if model == "news2":
        coef, intercept = b.fit_news2_probability(rule(train), train[LABEL].to_numpy(), seed)

        def prob(frame: pd.DataFrame) -> np.ndarray:
            return b.news2_probability(b.news2(frame), coef, intercept)

        return Scorer(
            "news2", rule, prob, {"news2_probability": {"coef": coef, "intercept": intercept}}
        )
    return Scorer(model, rule, None, {})


def _metrics_block(
    cohort: Cohort,
    scores: np.ndarray,
    threshold: float,
    weights: np.ndarray | None,
    reference: tuple[np.ndarray, np.ndarray],
) -> dict[str, object]:
    """Point estimates and (if bootstrap weights are given) 95 % CIs on one cohort."""
    alerts = scores >= threshold
    ranking = m.Ranking.build(scores, cohort.labels)
    parts = m.utility_parts(cohort.labels, alerts, cohort.patient, reference)
    events = m.patient_events(cohort.labels, alerts, cohort.patient)

    def stat(w: np.ndarray | None) -> dict[str, float]:
        row_w = None if w is None else w[cohort.patient]
        return {
            "auroc": ranking.auroc(row_w),
            "auprc": ranking.auprc(row_w),
            "utility": parts.normalized(w),
            "alert_rate": m.alert_rate(alerts, cohort.patient, w),
            **m.event_metrics(events, w),
        }

    point = stat(None)
    out: dict[str, object] = {
        "patients": cohort.n_patients,
        "septic_patients": int(events.septic.sum()),
        "septic_from_row_zero": int(events.from_row_zero.sum()),
        "rows": len(cohort.labels),
        "threshold": threshold,
        "point": point,
    }
    if weights is not None:
        ci = m.bootstrap_ci(stat, weights)
        out["ci95"] = {k: list(v) for k, v in ci.items()}
    return out


def _subgroups(
    cohort: Cohort, scores: np.ndarray, threshold: float, reference: tuple[np.ndarray, np.ndarray]
) -> dict[str, object]:
    """Point estimates by sex and age group (protocol section 5); no CIs."""
    first = np.r_[True, cohort.patient[1:] != cohort.patient[:-1]]
    gender = cohort.frame["Gender"].to_numpy()[first]
    age = cohort.frame["Age"].to_numpy()[first]
    groups = {
        "gender_0": gender == 0,
        "gender_1": gender == 1,
        "age_lt_65": age < 65,
        "age_ge_65": age >= 65,
    }
    out: dict[str, object] = {}
    for name, keep_patient in groups.items():
        rows = keep_patient[cohort.patient]
        if not rows.any():
            out[name] = {"patients": 0}
            continue
        sub = Cohort.of(cohort.frame[rows])
        ref = (reference[0][keep_patient], reference[1][keep_patient])
        block = _metrics_block(sub, scores[rows], threshold, None, ref)
        point = block["point"]
        assert isinstance(point, dict)
        out[name] = {"patients": block["patients"], **point}
    return out


@dataclass
class TargetContext:
    """Everything about the target hospital that does not depend on the model."""

    full: Cohort
    full_reference: tuple[np.ndarray, np.ndarray]
    full_weights: np.ndarray
    calibration: Cohort
    rest: Cohort
    rest_reference: tuple[np.ndarray, np.ndarray]
    rest_weights: np.ndarray


def target_context(frame: pd.DataFrame, splits: dict[str, set[str]], seed: int) -> TargetContext:
    full = Cohort.of(frame)
    rest = full.subset(splits["train"] | splits["val"])
    return TargetContext(
        full=full,
        full_reference=m.reference_utilities(full.labels, full.patient),
        full_weights=m.bootstrap_weights(full.n_patients, RESAMPLES, seed),
        calibration=full.subset(splits["calibration"]),
        rest=rest,
        rest_reference=m.reference_utilities(rest.labels, rest.patient),
        rest_weights=m.bootstrap_weights(rest.n_patients, RESAMPLES, seed),
    )


def evaluate_model(
    model: str,
    direction: str,
    cfg: Config,
    source: pd.DataFrame,
    source_splits: dict[str, set[str]],
    target: TargetContext,
) -> tuple[dict[str, object], Scorer]:
    features = [c for c in source.columns if c not in KEYS]
    train = source[source["pid"].isin(source_splits["train"])]
    val = source[source["pid"].isin(source_splits["val"])]
    scorer = fit_scorer(model, train, features, cfg.seed)

    threshold, val_rate = m.budget_threshold(scorer.score(val), cfg.alarm_budget)
    target_scores = scorer.score(target.full.frame)
    strict = _metrics_block(
        target.full, target_scores, threshold, target.full_weights, target.full_reference
    )
    strict["source_validation_alert_rate"] = val_rate
    strict["subgroups"] = _subgroups(target.full, target_scores, threshold, target.full_reference)
    if scorer.probability is not None:
        probs = scorer.probability(target.full.frame)
        strict["ece"] = m.ece(probs, target.full.labels)
        strict["reliability"] = m.reliability(probs, target.full.labels).to_dict("list")

    adapted_threshold, cal_rate = m.budget_threshold(
        scorer.score(target.calibration.frame), cfg.alarm_budget
    )
    adapted = _metrics_block(
        target.rest,
        scorer.score(target.rest.frame),
        adapted_threshold,
        target.rest_weights,
        target.rest_reference,
    )
    adapted["target_calibration_alert_rate"] = cal_rate

    source_h, target_h = DIRECTIONS[direction]
    result: dict[str, object] = {
        "model": model,
        "model_label": MODEL_LABELS[model],
        "direction": direction,
        "source": source_h,
        "target": target_h,
        "alarm_budget": cfg.alarm_budget,
        "seed": cfg.seed,
        "bootstrap_resamples": RESAMPLES,
        "strict_external": strict,
        "deployment_adaptation": adapted,
        "fitted": _fitted_summary(scorer),
    }
    if model == "news2":
        cf_threshold, _ = m.budget_threshold(b.news2(val, carry_hours=24), cfg.alarm_budget)
        cf = _metrics_block(
            target.full,
            b.news2(target.full.frame, carry_hours=24).astype(np.float64),
            cf_threshold,
            None,
            target.full_reference,
        )
        result["sensitivity_fio2_carry_24h"] = cf
    return result, scorer


def plain(value: object) -> object:
    """JSON-safe copy: numpy scalars to Python, NaN/inf to null (strict JSON)."""
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple | np.ndarray):
        return [plain(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _fitted_summary(scorer: Scorer) -> object:
    """Result files keep small fitted values only; LR coefficients live in models/."""
    logistic = scorer.fitted.get("logistic")
    if isinstance(logistic, Mapping):
        return {"logistic_features": len(logistic["features"]), "stored_in": "models/baselines"}
    return scorer.fitted


def write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(plain(document), indent=1, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


def save_logistic(models_dir: Path, direction: str, scorer: Scorer, cfg: Config) -> Path:
    """Model as JSON next to its feature_schema.json (never pickle; ADR 0004)."""
    folder = models_dir / "baselines" / f"lr_{direction}"
    write_json(folder / "model.json", scorer.fitted)
    write_json(folder / "feature_schema.json", schema_document(cfg.features))
    return folder


def run(
    models: list[str],
    directions: list[str],
    cfg: Config,
    data_dir: Path,
    splits_dir: Path,
    results_dir: Path,
    models_dir: Path,
    figures_dir: Path,
) -> list[Path]:
    from sepsiscope.evaluation import figures

    written: list[Path] = []
    for direction in directions:
        source_h, target_h = DIRECTIONS[direction]
        source = read_features(data_dir, source_h)
        target = target_context(
            read_features(data_dir, target_h), _split_pids(splits_dir, target_h), cfg.seed
        )
        source_splits = _split_pids(splits_dir, source_h)
        probabilities: dict[str, np.ndarray] = {}
        reliability: dict[str, pd.DataFrame] = {}
        for model in models:
            result, scorer = evaluate_model(model, direction, cfg, source, source_splits, target)
            path = results_dir / f"{model}_{direction}.json"
            write_json(path, result)
            written.append(path)
            if model == "lr":
                save_logistic(models_dir, direction, scorer, cfg)
            if scorer.probability is not None:
                p = scorer.probability(target.full.frame)
                probabilities[model] = p
                reliability[model] = m.reliability(p, target.full.labels)
        if probabilities:
            curve = m.decision_curve(target.full.labels, probabilities, DCA_THRESHOLDS)
            path = results_dir / f"decision_curve_{direction}.json"
            columns = {str(c): curve[c].tolist() for c in curve.columns}
            write_json(path, {"direction": direction, **columns})
            written.append(path)
            written.append(figures.decision_curve(curve, direction, figures_dir))
            written.append(figures.reliability(reliability, direction, figures_dir))
        del source, target
    return written
