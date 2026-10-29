# ──────────────────────────────────────────────
#  finbot — Pydantic Models
# ──────────────────────────────────────────────

from pydantic import BaseModel
from typing import Optional


# ── Chat ───────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    type: str           # "token" | "ask_format" | "report_ready" | "error"
    content: str        # the text token or message
    symbol: Optional[str] = None
    url: Optional[str] = None


# ── Financial ──────────────────────────────────

class BasicInfo(BaseModel):
    symbol: str
    ltp: Optional[float] = None
    wh52: Optional[str] = None
    wl52: Optional[float] = None
    p_e: Optional[float] = None
    nav: Optional[float] = None
    dividend_yield: Optional[str] = None
    market_cap: Optional[float] = None
    trailing_pe: Optional[float] = None
    total_share: Optional[float] = None
    paid_up_capital: Optional[float] = None
    year_end: Optional[str] = None
    year_value: Optional[str] = None
    last_update: Optional[str] = None


class DividendRecord(BaseModel):
    symbol: str
    year: Optional[str] = None
    cash: Optional[float] = None
    stock: Optional[float] = None
    yield_pct: Optional[float] = None
    rights: Optional[float] = None


class AnnualEPS(BaseModel):
    symbol: str
    year_value: Optional[str] = None
    eps: Optional[float] = None


class QuarterlyEPS(BaseModel):
    symbol: str
    quarter_date: Optional[str] = None
    quarter: Optional[str] = None
    eps: Optional[float] = None


class CorporateEvent(BaseModel):
    symbol: str
    action_date: Optional[str] = None
    news: Optional[str] = None
    actual_value: Optional[str] = None
    forecast_value: Optional[str] = None
    previous_value: Optional[str] = None
    impact: Optional[str] = None


class DividendAction(BaseModel):
    symbol: str
    declaration_date: Optional[str] = None
    dividend: Optional[str] = None
    record_date: Optional[str] = None
    agm_date: Optional[str] = None
