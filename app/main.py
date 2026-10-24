from __future__ import annotations

import asyncio
import json
import os
import glob
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import APP_HOST, APP_PORT, STATE_NAME, WEB_DIR
from database import init_db
from models import (
    get_dashboard_stats, get_scan_runs, get_tender_by_number, get_tender_history,
    list_departments, list_tenders, get_company_analysis, set_watermark
)

BASE_DIR = Path(__file__).resolve().parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.state_name = STATE_NAME
    yield

app = FastAPI(title="KPPP Platform", version="0.2.0", lifespan=lifespan)
app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")

@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "state": STATE_NAME}

@app.get("/dashboard")
def dashboard() -> dict:
    stats = get_dashboard_stats()
    return {
        "state": STATE_NAME,
        "tenders": list_tenders(limit=15),
        "departments": list_departments(),
        "stats": stats,
        "watcher": {"status": "running"},
        "latest_run": stats.get("last_run"),
        "last_successful_scan_date": stats.get("last_successful_scan_date"),
        "tender_count": stats.get("tender_count"),
        "department_count": stats.get("department_count"),
    }

@app.get("/tenders")
def tenders(
    department: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
) -> list[dict]:
    return list_tenders(limit=limit, department_code=department, status=status, search=search)

@app.get("/my-tenders")
def my_tenders(
    unknown_only: bool = Query(default=False),
    limit: int = Query(default=100)
) -> list[dict]:
    return list_tenders(limit=limit, my_tenders_only=True, unknown_only=unknown_only)

@app.get("/tender/{tender_number:path}")
def tender(tender_number: str) -> dict:
    record = get_tender_by_number(tender_number)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Tender not found: {tender_number}")
    record["timeline"] = get_tender_history(tender_number)
    return record

@app.get("/tender-file/{tender_number:path}/{filename}")
def serve_tender_file(tender_number: str, filename: str):
    safe_num = tender_number.replace("/", "_")
    matched = glob.glob(str(BASE_DIR / "data" / "raw" / "**" / safe_num / "docs" / filename), recursive=True)
    if not matched:
        matched = glob.glob(str(BASE_DIR / "data" / "raw" / "**" / safe_num / filename), recursive=True)
    if not matched:
        matched = glob.glob(str(BASE_DIR / "data" / "raw" / safe_num / filename), recursive=True)
    if not matched:
        # Check kk_extraction probe
        matched = glob.glob(rf"C:\Users\Admin\Desktop\kppp_probe\kk_extraction\raw\*{safe_num}*.xlsx")
    if matched and os.path.exists(matched[0]):
        return FileResponse(matched[0], filename=filename)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/company/kk-allianze")
def company_kk_allianze() -> dict:
    return get_company_analysis()

@app.get("/departments")
def departments() -> list[dict]:
    return list_departments()

@app.get("/coverage")
def coverage() -> dict:
    return {
        "departments": list_departments(),
        "scan_runs": get_scan_runs(limit=10)
    }

@app.get("/events")
async def events():
    async def event_stream():
        yield f"data: {json.dumps({'type': 'heartbeat', 'message': 'KPPP platform online', 'state': STATE_NAME})}\n\n"
        while True:
            payload = {
                "type": "tick",
                "message": "Watching 17 departments",
                "state": STATE_NAME,
                "status": "running",
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(15)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=APP_HOST, port=APP_PORT, reload=False)
