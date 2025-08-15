# toolbox.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple
import pandas as pd

# Expected header names in ranges CSV (case-insensitive):
# Parameter, Min, Max
REQUIRED_HEADERS = ("parameter", "min", "max")


def load_ranges(csv_path: Path) -> Dict[str, Tuple[float, float]]:
    """
    Load dynamic ranges from an XLSX file with columns: Parameter, Min, Max (case-insensitive).
    Returns a dict like { "Water Temperature (°C)": (26.0, 35.0), ... }.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Ranges file not found: {csv_path}")

    df = pd.read_excel(csv_path)  # Changed from read_csv to read_excel

    # normalize headers
    lower_map = {c.lower(): c for c in df.columns}
    if not all(h in lower_map for h in REQUIRED_HEADERS):
        raise ValueError(
            f"Ranges file must contain columns: Parameter, Min, Max (any case). Found: {list(df.columns)}"
        )

    pcol, mincol, maxcol = (lower_map[h] for h in REQUIRED_HEADERS)

    # drop rows with missing essentials
    df = df.dropna(subset=[pcol, mincol, maxcol])

    # coerce to numeric for min/max
    df[mincol] = pd.to_numeric(df[mincol], errors="coerce")
    df[maxcol] = pd.to_numeric(df[maxcol], errors="coerce")
    df = df.dropna(subset=[mincol, maxcol])

    ranges: Dict[str, Tuple[float, float]] = {}
    for _, row in df.iterrows():
        param = str(row[pcol]).strip()
        ranges[param] = (float(row[mincol]), float(row[maxcol]))
    return ranges


def highlight_out_of_range(df: pd.DataFrame, ranges: Dict[str, Tuple[float, float]]) -> pd.io.formats.style.Styler:
    """
    Returns a Styler with cells outside [min, max] highlighted in red.
    Only columns present in 'ranges' are evaluated; others are untouched.
    """
    def style_column(col: pd.Series):
        name = col.name
        if name not in ranges:
            return [""] * len(col)
        min_v, max_v = ranges[name]
        # Ensure numeric comparison
        numeric = pd.to_numeric(col, errors="coerce")
        mask = (numeric < min_v) | (numeric > max_v)
        return ["background-color: #d92d20; color: white;" if out else "" for out in mask]

    return df.style.apply(style_column, axis=0)


def load_maintenance(csv_path: Path) -> Dict[str, Tuple[float, float]]:
    """
    Load dynamic ranges from an XLSX file with columns: Parameter, Min, Max (case-insensitive).
    Returns a dict like { "Water Temperature (°C)": (26.0, 35.0), ... }.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Ranges file not found: {csv_path}")

    df = pd.read_excel(csv_path)  # Changed from read_csv to read_excel

    # normalize headers
    lower_map = {c.lower(): c for c in df.columns}
    if not all(h in lower_map for h in REQUIRED_HEADERS):
        raise ValueError(
            f"Ranges file must contain columns: Parameter, Min, Max (any case). Found: {list(df.columns)}"
        )

    pcol, mincol, maxcol = (lower_map[h] for h in REQUIRED_HEADERS)

    # drop rows with missing essentials
    df = df.dropna(subset=[pcol, mincol, maxcol])

    # coerce to numeric for min/max
    df[mincol] = pd.to_numeric(df[mincol], errors="coerce")
    df[maxcol] = pd.to_numeric(df[maxcol], errors="coerce")
    df = df.dropna(subset=[mincol, maxcol])

    ranges: Dict[str, Tuple[float, float]] = {}
    for _, row in df.iterrows():
        param = str(row[pcol]).strip()
        ranges[param] = (float(row[mincol]), float(row[maxcol]))
    return ranges

