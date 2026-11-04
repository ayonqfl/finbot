# finbot - Export API Endpoint
# GET /export -> FileResponse (PDF or CSV)
# Supports exporting query results directly via SQL or generating report on the fly.

import os
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from app.core.query_generator import execute_raw_sql, validate_sql, generate_and_execute
from app.services.db_tools import symbol_exists
from app.services.report import generate_csv, generate_pdf

router = APIRouter()


@router.get("/")
async def export_report(
    symbol:      str = Query(..., description="DSE stock symbol e.g. AOL, PTL, GP"),
    fmt:         str = Query(..., description="File format: pdf | csv"),
    sql:         str | None = Query(None, description="The SELECT query to export (if already generated)"),
    data_type:   str | None = Query(None, description="Report type / topic description"),
    report_type: str = Query("report", description="Label used in the filename and PDF header"),
):
    """
    Generate and return a PDF or CSV report.
    Supports:
      1. Pre-generated SQL from the chat agent
      2. Dynamic on-the-fly query generation when SQL is not provided
    """
    if not symbol or symbol.strip().lower() in ("null", "undefined", ""):
        raise HTTPException(status_code=400, detail="Missing or invalid stock symbol.")

    symbol = symbol.upper().strip()
    fmt    = fmt.lower().strip()

    if fmt not in ("pdf", "csv"):
        raise HTTPException(status_code=400, detail="Format must be 'pdf' or 'csv'.")

    # Validate symbol exists in basic_info
    if not symbol_exists(symbol):
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found in database.")

    rows = []
    # Path 1: SQL query is provided
    if sql and sql.strip():
        ok, reason = validate_sql(sql)
        if not ok:
            raise HTTPException(status_code=400, detail=f"Invalid SQL: {reason}")
        rows, db_error = execute_raw_sql(sql)
        if db_error:
            raise HTTPException(status_code=500, detail=f"Query failed: {db_error}")

    # Path 2: No SQL provided -> dynamically generate query for symbol
    if not rows:
        topic = data_type if (data_type and data_type.lower() not in ("undefined", "null")) else "financial"
        gen_prompt = f"Export comprehensive {topic} report data for symbol {symbol}"
        result = await generate_and_execute(gen_prompt)
        if not result.ok or not result.rows:
            raise HTTPException(
                status_code=404,
                detail=f"No report data found for {symbol} ({result.error or 'empty result'})."
            )
        rows = result.rows

    # Label for file naming
    clean_label = (data_type or report_type or "report").replace(" ", "_").lower()

    # Generate file
    if fmt == "csv":
        filepath   = generate_csv(rows, symbol, clean_label)
        media_type = "text/csv"
    else:
        filepath   = generate_pdf(rows, symbol, clean_label)
        media_type = "application/pdf"

    filename = os.path.basename(filepath)
    return FileResponse(
        path=filepath,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
