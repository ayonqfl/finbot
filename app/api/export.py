# finbot — Export API Endpoint
# GET /export -> FileResponse (PDF or CSV)
# Supports:
#   1. Fetching cached report data by report_id (instant, secure, no re-querying)
#   2. Pre-generated SQL (if provided)
#   3. Dynamic query generation on the fly for single symbols or all symbols

import os
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from app.core.query_generator import execute_raw_sql, validate_sql, generate_and_execute
from app.services.db_tools import symbol_exists
from app.services.report import generate_csv, generate_pdf
from app.services.report_store import get_report_data

router = APIRouter()


@router.get("/")
async def export_report(
    symbol:      str = Query("ALL", description="DSE stock symbol e.g. AOL, PTL, GP, or ALL for all symbols"),
    fmt:         str = Query(..., description="File format: pdf | csv"),
    report_id:   str | None = Query(None, description="Report token from chat for instant download"),
    sql:         str | None = Query(None, description="The SELECT query to export (if already generated)"),
    data_type:   str | None = Query(None, description="Report type / topic description"),
    report_type: str | None = Query("report", description="Label used in the filename and PDF header"),
):
    """
    Generate and return a PDF or CSV report.
    Supports single symbols (e.g. PTL) as well as all symbols (ALL).
    """
    fmt = fmt.lower().strip()
    if fmt not in ("pdf", "csv"):
        raise HTTPException(status_code=400, detail="Format must be 'pdf' or 'csv'.")

    # Normalize symbol
    clean_sym = (symbol or "ALL").upper().strip()
    if clean_sym in ("NULL", "UNDEFINED", ""):
        clean_sym = "ALL"

    rows = []
    # Safe label resolution
    lbl_dt = data_type if (data_type and isinstance(data_type, str)) else None
    lbl_rt = report_type if (report_type and isinstance(report_type, str)) else "report"
    clean_label = (lbl_dt or lbl_rt or "report").replace(" ", "_").lower()

    # Path 1: Cached report from chat session (Fastest & 100% accurate)
    cached = get_report_data(report_id)
    if cached and cached.get("rows"):
        rows = cached["rows"]
        clean_sym = cached.get("symbol", clean_sym)
        if cached.get("data_type"):
            clean_label = cached["data_type"].replace(" ", "_").lower()

    # Path 2: Raw SQL provided directly
    if not rows and sql and sql.strip():
        ok, reason = validate_sql(sql)
        if not ok:
            raise HTTPException(status_code=400, detail=f"Invalid SQL: {reason}")
        rows, db_error = execute_raw_sql(sql)
        if db_error:
            raise HTTPException(status_code=500, detail=f"Query failed: {db_error}")

    # Path 3: Generate query dynamically (cold fallback)
    if not rows:
        topic = (data_type or "financial data").replace("_", " ")

        is_all = clean_sym in ("ALL", "ALL_SYMBOLS", "MARKET")
        if not is_all and not symbol_exists(clean_sym):
            raise HTTPException(status_code=404, detail=f"Symbol '{clean_sym}' not found in database.")

        if is_all:
            gen_prompt = f"Export {topic} for all symbols across the market"
        else:
            gen_prompt = f"Export {topic} for symbol {clean_sym}"

        result = await generate_and_execute(gen_prompt)
        if not result.ok or not result.rows:
            raise HTTPException(
                status_code=404,
                detail=f"No report data found ({result.error or 'empty result'})."
            )
        rows = result.rows

    # Generate file
    if fmt == "csv":
        filepath   = generate_csv(rows, clean_sym, clean_label)
        media_type = "text/csv"
    else:
        filepath   = generate_pdf(rows, clean_sym, clean_label)
        media_type = "application/pdf"

    filename = os.path.basename(filepath)
    return FileResponse(
        path=filepath,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
