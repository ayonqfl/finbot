#  finbot — Database Utility Helpers
#  NOTE: Hardcoded query functions (get_ltp, get_dividend_history, etc.) have
#  been superseded by the dynamic SQL pipeline in app/core/query_generator.py.
#  Only the shared utilities below are still active.

from decimal import Decimal
from datetime import date, datetime

from sqlalchemy import text

from app.core.database import engine


# Serialization helpers (shared with query_generator)

def _serialize_val(v):
    """Ensure Decimal / date / datetime are JSON-serialisable."""
    if isinstance(v, Decimal):
        return int(v) if v % 1 == 0 else float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _rows_to_dicts(result) -> list[dict]:
    """Convert SQLAlchemy CursorResult rows → list of JSON-serialisable dicts."""
    keys = list(result.keys())
    return [
        {k: _serialize_val(v) for k, v in zip(keys, row)}
        for row in result.fetchall()
    ]


def _sym(symbol: str) -> str:
    """Normalise a DSE symbol: UPPER-CASE and stripped."""
    return symbol.upper().strip()


# Symbol existence check
def symbol_exists(symbol: str) -> bool:
    """
    Return True if the symbol exists in public.basic_info.
    Used by agent.py for symbol extraction heuristics.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM public.basic_info WHERE symbol = :sym LIMIT 1"),
                {"sym": _sym(symbol)},
            )
            return result.fetchone() is not None
    except Exception:
        return False
