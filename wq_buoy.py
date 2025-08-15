# wq_buoy.py
import io
from pathlib import Path
import pandas as pd

from toolbox import load_ranges, highlight_out_of_range


def _read_dataframe_from_bytes(upload_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Reads CSV or Excel into a DataFrame from raw bytes based on filename extension.
    Defaults to CSV if unrecognized.
    """
    suffix = Path(filename).suffix.lower()
    bio = io.BytesIO(upload_bytes)

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(bio)
    # default to CSV
    return pd.read_csv(bio)


def generate_highlighted_excel_from_upload(
    upload_bytes: bytes,
    filename: str,
    ranges_csv_path: Path,
    out_path: Path,
) -> Path:
    """
    Core pipeline:
    - Parse uploaded file into a DataFrame
    - Load ranges from CSV
    - Apply highlighting
    - Write to Excel at out_path
    """
    df = _read_dataframe_from_bytes(upload_bytes, filename)

    # Normalize numeric columns to ensure comparisons work (only for columns that appear in ranges)
    ranges_map = load_ranges(ranges_csv_path)
    for col in df.columns:
        if col in ranges_map:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    styled = highlight_out_of_range(df, ranges_map)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    styled.to_excel(out_path, engine="openpyxl")
    return out_path
