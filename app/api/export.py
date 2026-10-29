# ──────────────────────────────────────────────
#  finbot — Export API Endpoint
#  GET /export → FileResponse (PDF or CSV)
# ──────────────────────────────────────────────

import os
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from app.services.db_tools import (
    get_dividend_history, get_annual_eps, get_quarterly_eps,
    get_corporate_events, get_dividend_declaration, get_fundamentals,
    symbol_exists
)
from app.services.report import generate_csv, generate_pdf

router = APIRouter()

# Map data_type param → fetcher function
DATA_FETCHERS = {
    "dividend_history":   get_dividend_history,
    "annual_eps":         get_annual_eps,
    "quarterly_eps":      get_quarterly_eps,
    "corporate_events":   get_corporate_events,
    "dividend_action":    get_dividend_declaration,
    "fundamentals":       get_fundamentals,
}


@router.get("/")
async def export_report(
    symbol:    str = Query(..., description="DSE stock symbol e.g. PTL"),
    data_type: str = Query(..., description="Report type: dividend_history | annual_eps | quarterly_eps | corporate_events | dividend_action | fundamentals"),
    fmt:       str = Query(..., description="File format: pdf | csv"),
):
    """
    Generate and return a PDF or CSV report.

    Example:
      GET /export?symbol=PTL&data_type=dividend_history&fmt=pdf
    """
    symbol    = symbol.upper().strip()
    fmt       = fmt.lower().strip()
    data_type = data_type.lower().strip()

    # Validate symbol
    if not symbol_exists(symbol):
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found in database.")

    # Validate data_type
    if data_type not in DATA_FETCHERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown data_type '{data_type}'. Allowed: {list(DATA_FETCHERS.keys())}"
        )

    # Validate format
    if fmt not in ("pdf", "csv"):
        raise HTTPException(status_code=400, detail="Format must be 'pdf' or 'csv'.")

    # Fetch data
    fetcher = DATA_FETCHERS[data_type]
    data = fetcher(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"No {data_type} data found for {symbol}.")

    # Ensure list
    if isinstance(data, dict):
        data = [data]

    # Generate file
    if fmt == "csv":
        filepath = generate_csv(data, symbol, data_type)
        media_type = "text/csv"
        filename   = os.path.basename(filepath)
    else:
        filepath = generate_pdf(data, symbol, data_type)
        media_type = "application/pdf"
        filename   = os.path.basename(filepath)

    return FileResponse(
        path=filepath,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
