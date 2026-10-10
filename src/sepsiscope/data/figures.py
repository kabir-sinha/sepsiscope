"""EDA figures, written as reproducible PNG files with no metadata.

Reproducibility: fixed size, dpi and font (DejaVu Sans, shipped with matplotlib), the
non-interactive Agg backend, no randomness, and ``metadata={"Software": None}`` so the
file has no text chunk. Saving the same data twice gives identical bytes.

Colours: blue = hospital A / non-septic, orange = hospital B / septic, grey = missing
(a colour-vision-deficiency-checked pair). Every figure's numbers are also in a table
in ``docs/eda_findings.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#b4b2ab"
INK, MUTED, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3df"
DPI = 150
FORBIDDEN_PNG_CHUNKS = frozenset({b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"tIME"})

# Typed loosely: matplotlib's stubs want a Literal key type for rc settings.
STYLE: Any = {
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "legend.frameon": False,
    "svg.hashsalt": "sepsiscope",
}


def _new(width: float, height: float, ncols: int = 1) -> tuple[Figure, list[Axes]]:
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(1, ncols, figsize=(width, height), dpi=DPI, sharey=ncols > 1)
    return fig, list(np.atleast_1d(axes))


def save(fig: Figure, path: Path) -> Path:
    """Save as PNG without any text/time metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(STYLE):
        fig.savefig(path, format="png", dpi=DPI, metadata={"Software": None})
    plt.close(fig)
    return path


def png_chunk_types(path: Path) -> list[bytes]:
    """The chunk types of a PNG file, in order (used by the metadata test and hook)."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path.name} is not a PNG file")
    chunks, pos = [], 8
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        chunks.append(data[pos + 4 : pos + 8])
        pos += 12 + length
    return chunks


def _paired_barh(ax: Axes, table: pd.DataFrame, xlabel: str) -> None:
    y = np.arange(len(table))
    ax.barh(y - 0.2, table["A"], height=0.36, color=BLUE, label="Hospital A")
    ax.barh(y + 0.2, table["B"], height=0.36, color=ORANGE, label="Hospital B")
    ax.set_yticks(y, list(table.index))
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)
    ax.margins(y=0.01)


def missingness_figure(missing: pd.DataFrame) -> Figure:
    table = (missing * 100).sort_values("A", ascending=False)
    with plt.rc_context(STYLE):
        fig, (ax,) = _new(7.0, 9.0)
        _paired_barh(ax, table, "Rows with the variable missing (%)")
        ax.set_xlim(0, 100)
        ax.set_title("Missingness per variable, by hospital")
        ax.legend(loc="lower left")
        fig.tight_layout()
    return fig


def frequency_figure(per_day: pd.DataFrame) -> Figure:
    table = per_day.sort_values("A", ascending=False)
    with plt.rc_context(STYLE):
        fig, (ax,) = _new(7.0, 8.0)
        _paired_barh(ax, table, "Measurements per patient-day (log scale)")
        ax.set_xscale("log")
        ax.set_title("How often each variable is measured")
        ax.legend(loc="lower right")
        fig.tight_layout()
    return fig


def stay_length_figure(patients: pd.DataFrame) -> Figure:
    bins = [float(edge) for edge in range(0, 337, 6)]
    with plt.rc_context(STYLE):
        fig, axes = _new(8.0, 3.6, ncols=2)
        for ax, hospital in zip(axes, ("A", "B"), strict=True):
            p = patients[patients["hospital"] == hospital]
            for flag, colour, label in ((False, BLUE, "Not septic"), (True, ORANGE, "Septic")):
                rows = p.loc[p["septic"] == flag, "rows"]
                weights = np.full(len(rows), 100 / max(len(rows), 1))
                ax.hist(rows, bins=bins, weights=weights, histtype="step", lw=1.6, color=colour,
                        label=f"{label} (n = {len(rows):,})")  # fmt: skip
            ax.set_title(f"Hospital {hospital}")
            ax.set_xlabel("Stay length (rows = hours recorded)")
            ax.legend(loc="upper right")
        axes[0].set_ylabel("Patients in group (%)")
        fig.suptitle("Stay length, septic vs not", x=0.01, ha="left", fontweight="bold")
        fig.tight_layout()
    return fig


def label_timing_figure(patients: pd.DataFrame) -> Figure:
    septic = patients[patients["septic"]]
    bins = [float(edge) for edge in range(0, 337, 6)]
    with plt.rc_context(STYLE):
        fig, (ax,) = _new(7.0, 3.6)
        for hospital, colour in (("A", BLUE), ("B", ORANGE)):
            values = septic.loc[septic["hospital"] == hospital, "first_positive_iculos"]
            weights = np.full(len(values), 100 / max(len(values), 1))
            ax.hist(values, bins=bins, weights=weights, histtype="step", lw=1.6, color=colour,
                    label=f"Hospital {hospital} (n = {len(values):,})")  # fmt: skip
        ax.set_xlabel("ICU hour (ICULOS) of the first positive label")
        ax.set_ylabel("Septic patients (%)")
        ax.set_title("When the label first turns positive")
        ax.legend(loc="upper right")
        fig.tight_layout()
    return fig


def shift_figure(shift: pd.DataFrame) -> Figure:
    table = shift.sort_values("js_values", ascending=False)
    y = np.arange(len(table))
    with plt.rc_context(STYLE):
        fig, (ax,) = _new(7.0, 9.0)
        ax.barh(y, table["js_values"], height=0.6, color=BLUE)
        ax.set_yticks(y, list(table.index))
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        ax.margins(y=0.01)
        ax.set_xlabel("Jensen-Shannon divergence of observed values, A vs B (0 = same)")
        ax.set_title("Distribution shift between hospitals, per variable")
        fig.tight_layout()
    return fig


def unit_figure(units: pd.DataFrame) -> Figure:
    parts = (("Unit1 = 1", BLUE), ("Unit2 = 1", ORANGE), ("missing", GREY))
    with plt.rc_context(STYLE):
        fig, (ax,) = _new(7.0, 2.4)
        left = np.zeros(len(units))
        for name, colour in parts:
            values = units[name].to_numpy() * 100
            ax.barh(list(units.index), values, left=left, color=colour, label=name,
                    edgecolor=SURFACE, linewidth=1.5)  # fmt: skip
            for i, (v, start) in enumerate(zip(values, left, strict=True)):
                if v >= 6:
                    ax.text(start + v / 2, i, f"{v:.0f}%", ha="center", va="center", color=INK)
            left += values
        ax.set_xlim(0, 100)
        ax.invert_yaxis()
        ax.set_xlabel("Rows (%)")
        ax.set_ylabel("Hospital")
        ax.grid(axis="y", visible=False)
        ax.set_title("ICU unit columns by hospital")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.45), ncols=3)
        fig.tight_layout()
    return fig
