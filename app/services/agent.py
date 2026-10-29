# ──────────────────────────────────────────────
#  finbot — LangChain Agent
#  Intent detection + DB tool routing
# ──────────────────────────────────────────────

import re
import json
from app.services.llm import ask_ollama, stream_ollama, strip_think_tags
from app.services import db_tools
from app.core.config import PRIMARY_MODEL

# ── System Prompt ──────────────────────────────

SYSTEM_PROMPT = """You are finbot, a financial data assistant for the Bangladesh DSE (Dhaka Stock Exchange) OMS system.

RULES YOU MUST FOLLOW:
1. You ONLY answer questions using data retrieved from the PostgreSQL database.
2. You NEVER recommend buying or selling any stock.
3. You CAN explain financial metrics, show trends, compare years, and help users understand data.
4. When a user asks for a report (PDF or CSV), you MUST ask which format they prefer — always.
5. If a symbol is not found in the database, politely say so.
6. Keep answers concise and data-focused.

AVAILABLE DATA (via database):
- LTP (Last Traded Price / yesterday_close)
- PE ratio, NAV, Dividend Yield, Market Cap, Trailing PE
- 52-week high/low
- Dividend history (yearly: cash, stock, yield %)
- Annual EPS history
- Quarterly EPS (Q1/Q2/Q3/Q4)
- Corporate events (dividend declarations, EPS announcements)
- AGM dates, record dates

RESPONSE FORMAT FOR SPECIAL ACTIONS:
- If you need to ask for report format, respond EXACTLY with:
  [ASK_FORMAT:SYMBOL:REPORT_TYPE]
  Example: [ASK_FORMAT:PTL:dividend_history]
- For normal answers, respond in plain friendly text.
- Do NOT make up data. Only use what is provided to you in the context.

SYMBOLS: Bangladesh DSE-listed stocks e.g. PTL, GP, BNIPLC, RENATA, WALTONHIL, SAMORITA, BSRMLTD etc.
"""

# ── Intent Detection ───────────────────────────

REPORT_KEYWORDS = [
    "report", "generate", "export", "download", "pdf", "csv",
    "file", "create report", "make report"
]

DATA_TYPE_MAP = {
    "dividend history": "dividend_history",
    "dividend":         "dividend_history",
    "eps":              "annual_eps",
    "earnings":         "annual_eps",
    "quarterly eps":    "quarterly_eps",
    "quarterly":        "quarterly_eps",
    "corporate event":  "corporate_events",
    "event":            "corporate_events",
    "fundamental":      "fundamentals",
    "ltp":              "ltp",
    "price":            "ltp",
}


def extract_symbol(text: str) -> str | None:
    """
    Extract a DSE symbol from the user message.
    Strategy:
      1. First check if any word in the message exists as a symbol in DB.
      2. If not found in DB, check for words written in ALL-CAPS by the user
         that are not common English words (potential symbol not in DB).
      3. Otherwise return None (general chat, greeting, or question without symbol).
    """
    noise = {
        "THE","AND","FOR","ARE","WAS","CAN","YOU","ALL","GET","LET",
        "ITS","HIS","HER","OUR","BUT","NOT","USE","HAS","HAD","OR",
        "OF","TO","IN","IS","IT","BE","AS","AT","SO","WE","DO",
        "ME","MY","WHAT","SHOW","GIVE","WANT","FIND","TELL","LIST",
        "LAST","LATEST","CHECK","LOOK","NEED","MAKE","SHOULD",
        "WOULD","COULD","WILL","FROM","WITH","THIS","THAT","THESE",
        "THOSE","HAVE","BEEN","ALSO","JUST","MORE","SOME","THEY",
        "THEIR","WERE","WHEN","THEN","HERE","THAN","INTO","OVER",
        "AFTER","UNDER","LIKE","ONLY","ABOUT","HIGH","LOW","WEEK",
        "YEAR","QUARTER","ANNUAL","MONTHLY","QUARTERLY","HISTORY",
        "REPORT","DATA","INFO","RATIO","PRICE","VALUE",
        "CURRENT","RECENT","EPS","LTP","NAV","BUY","SELL","STOCK",
        "MARKET","TRADE","SHARE","DIVIDEND","CORPORATE","EVENT",
        "AGM","PE","DISPLAY","FETCH","PLEASE","PDF","CSV","FILE",
        "HELLO","HI","HEY","GOOD","MORNING","EVENING","AFTERNOON",
        "HOW","WHO","WHY","WHERE","YES","NO","OK","THANKS","THANK",
        "FINBOT","BOT","ASSISTANT","HELP",
    }

    # 1. Check all tokens (case-insensitive) against database
    tokens = re.findall(r'\b[A-Za-z0-9&]{2,12}\b', text)
    for t in tokens:
        upper_t = t.upper()
        if upper_t not in noise and db_tools.symbol_exists(upper_t):
            return upper_t

    # 2. Check for tokens specifically typed in ALL-CAPS by the user (2+ chars)
    raw_caps = re.findall(r'\b[A-Z0-9&]{2,10}\b', text)
    caps_candidates = [c for c in raw_caps if c not in noise and not c.isdigit()]
    if caps_candidates:
        return caps_candidates[0]

    return None


def detect_report_intent(message: str) -> bool:
    """Returns True if user wants a report/export."""
    lower = message.lower()
    return any(kw in lower for kw in REPORT_KEYWORDS)


def detect_data_type(message: str) -> str:
    """
    Return the best matching data type from the message.
    Sort by phrase length descending so longer phrases win
    (e.g. 'quarterly eps' beats 'eps').
    """
    lower = message.lower()
    for phrase in sorted(DATA_TYPE_MAP.keys(), key=len, reverse=True):
        if phrase in lower:
            return DATA_TYPE_MAP[phrase]
    return "fundamentals"   # safe default


# ── Data Fetcher ───────────────────────────────

def fetch_data(symbol: str, data_type: str) -> tuple[list[dict] | dict | None, str]:
    """
    Fetch data from DB based on type.
    Returns (data, human_label).
    """
    fetchers = {
        "ltp":             (db_tools.get_ltp,                "LTP & Fundamentals"),
        "fundamentals":    (db_tools.get_fundamentals,        "Fundamental Data"),
        "dividend_history":(db_tools.get_dividend_history,    "Dividend History"),
        "annual_eps":      (db_tools.get_annual_eps,          "Annual EPS"),
        "quarterly_eps":   (db_tools.get_quarterly_eps,       "Quarterly EPS"),
        "corporate_events":(db_tools.get_corporate_events,    "Corporate Events"),
        "dividend_action": (db_tools.get_dividend_declaration,"Dividend Declaration"),
    }
    fn, label = fetchers.get(data_type, (db_tools.get_fundamentals, "Data"))
    return fn(symbol), label


# ── Main Agent ─────────────────────────────────

async def run_agent(user_message: str) -> dict:
    """
    Main agent entry point.
    Returns a structured response dict:
      { type, content, symbol, data_type, data, ask_format }
    """
    symbol    = extract_symbol(user_message)
    data_type = detect_data_type(user_message)
    wants_report = detect_report_intent(user_message)

    # ── Case 1: Report request — ask format first
    if wants_report and symbol:
        return {
            "type":      "ask_format",
            "symbol":    symbol,
            "data_type": data_type,
            "content":   f"I can prepare the **{data_type.replace('_',' ').title()}** report for **{symbol}**. Which format would you like?",
        }

    # ── Case 2: Data query — fetch from DB then ask LLM to explain
    if symbol:
        data, label = fetch_data(symbol, data_type)
        if not data:
            return {
                "type":    "text",
                "content": f"I couldn't find any **{label}** data for symbol **{symbol}** in the database. Please check the symbol name (e.g. PTL, GP, BNIPLC).",
            }

        # Build context for LLM
        data_str = json.dumps(data, default=str, indent=2)
        prompt = f"""{SYSTEM_PROMPT}

USER QUESTION: {user_message}

DATABASE DATA FOR {symbol} ({label}):
{data_str}

Please answer the user's question using only the data above. Be clear and concise.
"""
        answer = await ask_ollama(prompt, model=PRIMARY_MODEL)
        return {
            "type":    "text",
            "content": answer,
            "symbol":  symbol,
            "data":    data,
        }

    # ── Case 3: General chat (no symbol detected)
    prompt = f"""{SYSTEM_PROMPT}

USER MESSAGE: {user_message}

Respond helpfully. If the user needs to specify a symbol, ask them politely.
"""
    answer = await ask_ollama(prompt, model=PRIMARY_MODEL)
    return {
        "type":    "text",
        "content": answer,
    }
