"""Result figures: decision curves and reliability plots (metadata-free, reproducible PNG)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from sepsiscope.data.figures import BLUE, GREY, INK, ORANGE, _new, save

COLOURS = {"lr": BLUE, "news2": ORANGE, "lgbm": "#2e9e6b", "all": GREY, "none": INK}
LABELS = {
    "lr": "Logistic regression",
    "news2": "Modified NEWS2 (max 17), as probability",
    "lgbm": "LightGBM (Platt-calibrated)",
    "all": "Alert everyone",
    "none": "Alert no one",
}


def decision_curve(table: pd.DataFrame, direction: str, folder: Path) -> Path:
    fig, (ax,) = _new(6.0, 3.6)
    for model, part in table.groupby("model", sort=False):
        name = str(model)
        ax.plot(
            part["threshold"],
            part["net_benefit"],
            color=COLOURS.get(name, GREY),
            linestyle="--" if name in ("all", "none") else "-",
            label=LABELS.get(name, name),
        )
    lowest = table.loc[table["model"] != "all", "net_benefit"].min()
    ax.set_ylim(min(-0.005, float(lowest)), None)
    ax.set_xlabel("Threshold probability")
    ax.set_ylabel("Net benefit (per patient-hour)")
    ax.set_title(f"Decision curve, {direction} (strict external validation)")
    ax.legend(loc="upper right")
    return save(fig, folder / f"decision_curve_{direction}.png")


def reliability(tables: Mapping[str, pd.DataFrame], direction: str, folder: Path) -> Path:
    fig, (ax,) = _new(4.2, 4.0)
    top = max(float(t[["mean_predicted", "observed_rate"]].max().max()) for t in tables.values())
    ax.plot([0, top], [0, top], color=GREY, linestyle="--", label="Perfect calibration")
    for name, table in tables.items():
        ax.plot(
            table["mean_predicted"],
            table["observed_rate"],
            marker="o",
            markersize=3,
            color=COLOURS.get(name, GREY),
            label=LABELS.get(name, name),
        )
    ax.set_xlabel("Mean predicted probability (10 quantile bins)")
    ax.set_ylabel("Observed rate")
    ax.set_title(f"Reliability, {direction}")
    ax.legend(loc="upper left")
    return save(fig, folder / f"reliability_{direction}.png")
