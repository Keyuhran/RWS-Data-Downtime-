# main.py
import io
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, UploadFile, Form, File, Request
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from wq_buoy import generate_highlighted_excel_from_upload
from wq_buoy import _read_dataframe_from_bytes

from buoys import WQ_Buoy


# ----------------------------
# Config
# ----------------------------
DATA_DIR = Path("./data")
EXPORTS_DIR = Path("./exports")
RANGES_CSV = Path("./data/ranges/water_quality_ranges.xlsx")
EXCEL_NAME = "highlighted.xlsx"
EXCEL_PATH = EXPORTS_DIR / EXCEL_NAME

for p in (DATA_DIR, EXPORTS_DIR, RANGES_CSV.parent):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Upload Grid Backend", version="1.0.0")

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

# Serve /exports statically (handy in browser)
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR), html=False), name="exports")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = Path("index.html")
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>index.html not found</h1>"


@app.post("/api/upload")
async def upload_and_highlight(
    request: Request,
    month: str = Form(...),
    days: int = Form(...),
    file_1: UploadFile = File(...),
) -> JSONResponse:
    """
    Accepts one uploaded file (file_1), highlights out-of-range cells,
    writes ./exports/highlighted.xlsx, and returns a download URL.
    """
    try:
        # Optional: refresh ranges if you maintain them in a CSV
        # WQ_Buoy.refresh_ranges_from_csv(str(RANGES_CSV))

        # Read the uploaded file into a DataFrame
        content_bytes = await file_1.read()
        df = _read_dataframe_from_bytes(content_bytes, file_1.filename or "uploaded.csv")

        # 🔹 Only for OUTPUT: show "N/A" instead of blanks
        df_display = df.fillna("N/A")

        # Apply styling for out-of-range values
        styler = WQ_Buoy.highlight_out_of_range(df_display)

        # Save the styled Excel
        buf = io.BytesIO()
        try:
            # pandas >=1.4 supports na_rep on Styler.to_excel
            styler.to_excel(buf, engine="openpyxl", na_rep="N/A")
        except TypeError:
            # fallback if na_rep not supported
            styler.data = styler.data.fillna("N/A")
            styler.to_excel(buf, engine="openpyxl")

        buf.seek(0)
        with open(EXCEL_PATH, "wb") as f:
            f.write(buf.getvalue())

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "message": "Failed to process the uploaded file. Check the data formatting and ranges file.",
                "error": str(e),
            },
        )

    excel_exists = EXCEL_PATH.exists()
    excel_url = f"{str(request.base_url).rstrip('/')}/exports/{EXCEL_NAME}" if excel_exists else None

    return JSONResponse(
        content={
            "ok": True,
            "month": month,
            "days": days,
            "excel_available": bool(excel_exists),
            "excel_url": excel_url,
        }
    )


@app.get("/api/download/highlighted.xlsx")
def download_excel():
    if not EXCEL_PATH.exists():
        return PlainTextResponse("Excel file not found. Upload first.", status_code=404)
    return FileResponse(
        path=str(EXCEL_PATH),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=EXCEL_NAME,
    )

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = Path("index.html")
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>index.html not found</h1>"
