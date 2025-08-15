import pandas as pd
from typing import Dict, Tuple

# ---------- Config / CSV loader (above classes) ----------

DEFAULT_RANGES_CSV = "./data/ranges/water_quality_ranges.csv"

# Fixed schema (assumed columns in your data)
PARAM_COLS = [
    "Water Temperature (°C)",
    "Conductivity (μS/cm)",
    "Turbidity (NTU)",
    "Dissolved Oxygen (mg/L)",
    "pH",
    "Chlorophyll-a (μg/L)",
    "Crude Oil (ppm)",
    "Fine Oil (ppm)",
]

# Optional fallback (used if CSV missing/unreadable)
_FALLBACK_RANGES: Dict[str, Tuple[float, float]] = {
    "Water Temperature (°C)": (26.00, 35.00),
    "Conductivity (μS/cm)": (42000.00, 52000.0),
    "Turbidity (NTU)": (0.00, 25.00),
    "Dissolved Oxygen (mg/L)": (4.00, 10.00),
    "pH": (7.50, 9.00),
    "Chlorophyll-a (μg/L)": (0.00, 20.00),
    "Crude Oil (ppm)": (0.00, 0.500),
    "Fine Oil (ppm)": (0.00, 0.500),
}

def load_ranges_csv_simple(path: str = DEFAULT_RANGES_CSV) -> Dict[str, Tuple[float, float]]:
    """
    Reads ranges from a CSV with schema:
        parameter,min,max
        Water Temperature (°C),0,35
        ...
    Returns: { parameter_name: (min_val, max_val) }
    """
    try:
        df = pd.read_csv(path)
        required = {"parameter", "min", "max"}
        if not required.issubset(df.columns):
            raise ValueError(f"ranges CSV must have columns: {sorted(required)}")

        ranges: Dict[str, Tuple[float, float]] = {}
        for _, row in df.iterrows():
            p = str(row["parameter"]).strip()
            if p in PARAM_COLS:
                ranges[p] = (float(row["min"]), float(row["max"]))

        # Ensure we have all fixed params; otherwise fail back to defaults
        missing = [p for p in PARAM_COLS if p not in ranges]
        if missing:
            # Fall back to defaults for any missing, but keep CSV-provided ones
            for p in missing:
                ranges[p] = _FALLBACK_RANGES[p]
        return ranges

    except Exception:
        # If file missing or malformed, fall back to hardcoded defaults
        return dict(_FALLBACK_RANGES)


# ---------- Classes ----------

class WQ_Buoy:
    # Load from CSV at class definition time (calls the loader defined above)
    RANGES: Dict[str, Tuple[float, float]] = load_ranges_csv_simple()

    def __init__(
        self,
        name,
        waterTemperature,
        conductivity,
        turbidity,
        dissolvedOxygen,
        ph,
        chlorophyll_a,
        crudeOil,
        fineOil,
    ):
        self.name = name
        self.waterTemperature = waterTemperature
        self.conductivity = conductivity
        self.turbidity = turbidity
        self.dissolvedOxygen = dissolvedOxygen
        self.ph = ph
        self.chlorophyll_a = chlorophyll_a
        self.crudeOil = crudeOil
        self.fineOil = fineOil

    @classmethod
    def refresh_ranges_from_csv(cls, path: str = DEFAULT_RANGES_CSV) -> None:
        """Optional helper to reload ranges at runtime."""
        cls.RANGES = load_ranges_csv_simple(path)

    @classmethod
    def highlight_out_of_range(
        cls,
        df: pd.DataFrame,
        na_tokens=("N/A", "NA", "na", "n/a", "-", "—", ""),  # add/remove tokens as you like
    ):
        """
        - Yellow: cells that are NA-like (NaN or one of na_tokens)
        - Red: cells outside the configured range (overrides yellow when applicable)
        """
        def style_col(col: pd.Series):
            # 1) Base styles: NA-like -> yellow
            col_str = col.astype(str).str.strip()
            na_mask = col.isna() | col_str.isin(na_tokens)
            styles = ["background-color: #fff3b0;" if is_na else "" for is_na in na_mask]

            # 2) Overlay OOR: only for parameter columns we track
            rng = cls.RANGES.get(col.name)
            if rng:
                lo, hi = rng
                vals = pd.to_numeric(col, errors="coerce")
                oor_mask = (vals < lo) | (vals > hi)
                for i, is_oor in enumerate(oor_mask.fillna(False)):
                    if is_oor:
                        styles[i] = "background-color: #532fd3; color: white;"
            return styles

        return df.style.apply(style_col, axis=0)


class Weather_Buoy:
    def __init__(self, name, windSpeed, windDirection, relativeHumidity, atmosphericTemperature, netSolarRadiation):
        self.name = name
        self.windSpeed = windSpeed
        self.windDirection = windDirection
        self.relativeHumidity = relativeHumidity
        self.atmosphericTemperature = atmosphericTemperature
        self.netSolarRadiation = netSolarRadiation
