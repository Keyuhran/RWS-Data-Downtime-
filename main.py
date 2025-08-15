# main.py
import io
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd  

from fastapi import FastAPI, UploadFile, Form, File, Request
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from wq_buoy import _read_dataframe_from_bytes
from buoys import WQ_Buoy

# ----------------------------
# In-memory latest download (no disk writes, no tokens)
# ----------------------------
LATEST_DOWNLOAD_BYTES: Optional[bytes] = None

# ----------------------------
# Config
# ----------------------------
DATA_DIR = Path("./data")
RANGES_CSV = Path("./data/ranges/water_quality_ranges.xlsx")  # kept if you want to refresh later

for p in (DATA_DIR, RANGES_CSV.parent):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Upload Grid Backend", version="1.2.0")

# ----------------------------
# CORS (adjust to your frontend origin)
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = Path("index.html")
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>index.html not found</h1>"

# ----------------------------
# Helpers
# ----------------------------
def _highlight_df_bytes(dfs: List[Dict[str, object]]) -> bytes:
    """
    Accepts a list of { 'name': <sheet_name>, 'df': <pandas DataFrame> }.
    Applies WQ_Buoy.highlight_out_of_range to each and writes a single
    Excel workbook (one sheet per df) into bytes.
    """
    buf = io.BytesIO()
    # One writer for the whole workbook
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for entry in dfs:
            name: str = entry["name"]  # sheet name
            df = entry["df"]
            df_display = df.fillna("N/A")
            styler = WQ_Buoy.highlight_out_of_range(df_display)
            # Write each styled sheet; pass the open writer
            try:
                styler.to_excel(writer, sheet_name=name, na_rep="N/A")
            except TypeError:
                # older pandas Styler without na_rep support
                styler.data = styler.data.fillna("N/A")
                styler.to_excel(writer, sheet_name=name)
    buf.seek(0)
    return buf.getvalue()

def _unique_sheet_name(base: str, existing: set) -> str:
    """
    Ensure Excel sheet name is unique and <=31 chars.
    """
    proposed = (base or "Sheet").strip() or "Sheet"
    proposed = proposed[:31]
    name = proposed
    suffix = 2
    while name in existing:
        trimmed = proposed[: max(0, 31 - len(f"_{suffix}"))]
        name = f"{trimmed}_{suffix}"
        suffix += 1
    return name

# ----------------------------
# API: Upload up to 3 files → 1 workbook (3 sheets) in memory
# ----------------------------
@app.post("/api/upload")
async def upload_and_highlight(
    request: Request,
    month: str = Form(...),
    days: int = Form(...),
    file_1: Optional[UploadFile] = File(None),
    file_2: Optional[UploadFile] = File(None),
    file_3: Optional[UploadFile] = File(None),
) -> JSONResponse:
    """
    Accepts up to three uploaded files (file_1..file_3), applies highlighting,
    and exposes a stable download URL (/api/download/latest) served from memory.
    Nothing is written to disk.
    """
    try:
        # If you keep your dynamic ranges in XLSX and want to refresh at runtime:
        # WQ_Buoy.refresh_ranges_from_csv(str(RANGES_CSV))

        incoming: List[UploadFile] = [f for f in (file_1, file_2, file_3) if f is not None]
        if not incoming:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "message": "No files uploaded. Provide at least file_1."},
            )

        sheets: List[Dict[str, object]] = []
        existing_names: set = set()

        for idx, f in enumerate(incoming, start=1):
            content_bytes = await f.read()
            df = _read_dataframe_from_bytes(content_bytes, f.filename or f"uploaded_{idx}.csv")

            # Sheet name: prefer the filename stem; ensure uniqueness and <=31 chars
            base = (f.filename or f"Sheet{idx}").rsplit(".", 1)[0].strip() or f"Sheet{idx}"
            sheet_name = _unique_sheet_name(base, existing_names)
            existing_names.add(sheet_name)

            sheets.append({"name": sheet_name, "df": df})

        # Build a single workbook in memory
        excel_bytes = _highlight_df_bytes(sheets)

        # Save as the latest in-memory workbook (tokenless, reusable)
        global LATEST_DOWNLOAD_BYTES
        LATEST_DOWNLOAD_BYTES = excel_bytes

        base_url = str(request.base_url).rstrip("/")
        download_url = f"{base_url}/api/download/latest"

        # Back-compat fields for your existing UI
        return JSONResponse(
            content={
                "ok": True,
                "month": month,
                "days": days,
                "sheets": [s["name"] for s in sheets],
                "download_url": download_url,     # new stable URL
                "excel_url": download_url,        # legacy alias
                "excel_available": True,          # legacy flag
                "note": "Workbook is held in memory only (no disk write).",
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "message": "Failed to process the uploaded files. Check the data formatting and ranges file.",
                "error": str(e),
            },
        )

# ----------------------------
# API: Stable tokenless download (latest workbook)
# ----------------------------
@app.get("/api/download/latest")
def download_latest():
    global LATEST_DOWNLOAD_BYTES
    if LATEST_DOWNLOAD_BYTES is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": "No workbook available. Upload first."},
        )
    headers = {"Content-Disposition": 'attachment; filename="highlighted.xlsx"'}
    return Response(
        content=LATEST_DOWNLOAD_BYTES,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = Path("index.html")
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>index.html not found</h1>"
