# ──────────────────────────────────────────────
#  finbot — Database Query Tools
#  Rule: always use parameterized queries
#  Rule: always normalize symbol to UPPER
# ──────────────────────────────────────────────

from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import text
from app.core.database import engine


def _serialize_val(v):
    """Ensure values like Decimal, date, datetime are JSON serializable."""
    if isinstance(v, Decimal):
        return int(v) if v % 1 == 0 else float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _rows_to_dicts(result) -> list[dict]:
    """Convert SQLAlchemy result rows to list of JSON-serializable dicts."""
    keys = list(result.keys())
    return [
        {k: _serialize_val(v) for k, v in zip(keys, row)}
        for row in result.fetchall()
    ]


def _sym(symbol: str) -> str:
    """Normalize symbol input."""
    return symbol.upper().strip()


# ── 1. basic_info ──────────────────────────────

def get_ltp(symbol: str) -> dict | None:
    """Get Last Traded Price (yesterday_close) and key fields."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT symbol, yesterday_close AS ltp, p_e, nav,
                       dividend_yield, market_cap, trailing_pe,
                       wh52, wl52, total_share, paid_up_capital,
                       year_end, year_value, last_update
                FROM public.basic_info
                WHERE symbol = :sym
                LIMIT 1
            """),
            {"sym": _sym(symbol)}
        )
        rows = _rows_to_dicts(result)
        return rows[0] if rows else None


def get_fundamentals(symbol: str) -> dict | None:
    """Get all fundamental metrics for a symbol."""
    return get_ltp(symbol)   # same query — full basic_info row


# ── 2. dividend_history ────────────────────────

def get_dividend_history(symbol: str) -> list[dict]:
    """Get full yearly dividend history for a symbol."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT symbol, year, cash, stock, yield_pct, rights
                FROM public.dividend_history
                WHERE symbol = :sym
                ORDER BY year DESC
            """),
            {"sym": _sym(symbol)}
        )
        return _rows_to_dicts(result)


# ── 3. financial_annual ────────────────────────

def get_annual_eps(symbol: str) -> list[dict]:
    """Get annual EPS history for a symbol."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT symbol, year_value, eps
                FROM public.financial_annual
                WHERE symbol = :sym
                ORDER BY year_value DESC
            """),
            {"sym": _sym(symbol)}
        )
        return _rows_to_dicts(result)


# ── 4. financial_quarterly ─────────────────────

def get_quarterly_eps(symbol: str) -> list[dict]:
    """Get quarterly EPS history for a symbol."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT symbol, quarter_date, quarter, eps
                FROM public.financial_quarterly
                WHERE symbol = :sym
                ORDER BY quarter_date DESC
            """),
            {"sym": _sym(symbol)}
        )
        return _rows_to_dicts(result)


# ── 5. corporate_event ─────────────────────────

def get_corporate_events(symbol: str) -> list[dict]:
    """Get corporate events (EPS, dividends, AGM) for a symbol."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT symbol, declaration_date, action_date,
                       impact, news, actual_value, forecast_value, previous_value
                FROM public.corporate_event
                WHERE symbol = :sym
                ORDER BY action_date DESC
                LIMIT 20
            """),
            {"sym": _sym(symbol)}
        )
        return _rows_to_dicts(result)


# ── 6. dividend_corp_action ────────────────────

def get_dividend_declaration(symbol: str) -> list[dict]:
    """Get dividend declaration and AGM schedule for a symbol."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT symbol, declaration_date, dividend, record_date, agm_date
                FROM public.dividend_corp_action
                WHERE symbol = :sym
                ORDER BY id DESC
                LIMIT 10
            """),
            {"sym": _sym(symbol)}
        )
        return _rows_to_dicts(result)


# ── 7. Utility: symbol exists? ─────────────────

def symbol_exists(symbol: str) -> bool:
    """Check if symbol exists in basic_info."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM public.basic_info WHERE symbol = :sym LIMIT 1"),
            {"sym": _sym(symbol)}
        )
        return result.fetchone() is not None
