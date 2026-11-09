#  finbot — Agent (Dynamic SQL Pipeline)
#  Flow: user message → SQL generator → DB execute → LLM response formatter

import json
import re
import uuid

from app.core.query_generator import generate_and_execute
from app.services.llm import ask_llm
from app.services.db_tools import symbol_exists
from app.services.report_store import save_report_data

# System prompt for the *response formatter* step
# (This is NOT the SQL-generation prompt — that lives in query_generator.py)

_RESPONSE_SYSTEM_PROMPT = """\
You are finbot, a friendly financial data assistant for the Bangladesh DSE \
(Dhaka Stock Exchange) OMS system.

RULES:
1. You ONLY answer using the database data provided to you in this prompt.
2. You NEVER recommend buying or selling any stock.
3. You CAN explain financial metrics, spot trends, compare values, and help \
   users understand the numbers.
4. Format numbers neatly (use commas for thousands, 2 decimal places for \
   percentages and prices).
5. If the data is empty, politely say no records were found.
6. Keep your answer concise, accurate, and data-focused.
7. Do NOT make up any numbers or facts not present in the data.
8. If the data covers ALL symbols or a large dataset, provide a clear, structured \
   overview of the findings (mention total record count, key highlights, top performers, etc.).
"""


def _format_data_with_chunking(rows: list[dict]) -> tuple[str, str]:
    """
    Format rows for the LLM prompt using intelligent chunking:
    - For small datasets (<= 150 rows): sends all rows in JSON.
    - For large datasets (> 150 rows): calculates aggregate statistics across
      ALL rows, extracts sample chunks (beginning and end), and presents
      a structured dataset profile so the LLM has complete context without
      blowing up token limits.
    Returns: (formatted_data_json, note)
    """
    total_count = len(rows)
    if total_count <= 150:
        return json.dumps(rows, default=str, indent=2), ""

    # Large dataset chunking
    symbols = sorted(list({r.get("symbol") for r in rows if r.get("symbol")}))
    total_symbols = len(symbols)

    # Compute numeric statistics across the entire dataset
    numeric_stats = {}
    if rows:
        sample_row = rows[0]
        numeric_keys = [
            k for k, v in sample_row.items()
            if isinstance(v, (int, float)) and k not in ("id", "symbol")
        ]
        for key in numeric_keys:
            vals = [
                float(r[key]) for r in rows
                if r.get(key) is not None and isinstance(r[key], (int, float))
            ]
            if vals:
                numeric_stats[key] = {
                    "min": round(min(vals), 2),
                    "max": round(max(vals), 2),
                    "avg": round(sum(vals) / len(vals), 2),
                    "total_valid_records": len(vals),
                }

    first_chunk = rows[:30]
    last_chunk = rows[-15:]

    summary_payload = {
        "dataset_profile": {
            "total_records": total_count,
            "total_distinct_symbols": total_symbols,
            "sample_symbols_included": symbols[:20],
            "metrics_overview": numeric_stats,
        },
        "preview_first_chunk": first_chunk,
        "preview_recent_chunk": last_chunk,
    }

    note = (
        f"\n\nDATASET NOTE: The query returned {total_count} records across {total_symbols} symbols. "
        f"The full data profile and sample chunks are provided above. "
        f"Provide a clear, high-level summary of the entire dataset answering the user's question, "
        f"highlighting key trends and numbers. Note that the user can download the full report "
        f"with all {total_count} records."
    )

    return json.dumps(summary_payload, default=str, indent=2), note


def _build_response_prompt(user_message: str, rows: list[dict]) -> str:
    """Build the prompt that asks the LLM to narrate the query result."""
    data_str, chunk_note = _format_data_with_chunking(rows)
    row_count = len(rows)

    return (
        f"{_RESPONSE_SYSTEM_PROMPT}\n\n"
        f"USER QUESTION: {user_message}\n\n"
        f"DATA ({row_count} total record{'s' if row_count != 1 else ''}):\n{data_str}"
        f"{chunk_note}\n\n"
        f"Please answer the user's question clearly using only the data above."
    )


# Report intent detection
_REPORT_KEYWORDS = frozenset(
    ["report", "export", "download", "pdf", "csv", "file",
     "create report", "make report", "generate report"]
)


def _wants_report(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in _REPORT_KEYWORDS)


# All-symbols intent detection
_ALL_SYMBOLS_PATTERNS = [
    r"\ball\s+symbols?\b",
    r"\ball\s+stocks?\b",
    r"\ball\s+companies\b",
    r"\ball\s+listed\b",
    r"\bevery\s+stock\b",
    r"\bevery\s+symbol\b",
    r"\bentire\s+market\b",
    r"\bwhole\s+market\b",
    r"\bmarket[\s-]wide\b",
    r"\ball\s+data\b",
]


def _is_all_symbols_request(message: str) -> bool:
    lower = message.lower()
    return any(re.search(pat, lower) for pat in _ALL_SYMBOLS_PATTERNS)


# Symbol extractor (kept for specific symbol requests)
_NOISE_WORDS: set[str] = {
    "THE", "AND", "FOR", "ARE", "WAS", "CAN", "YOU", "ALL", "GET", "LET",
    "ITS", "HIS", "HER", "OUR", "BUT", "NOT", "USE", "HAS", "HAD", "OR",
    "OF", "TO", "IN", "IS", "IT", "BE", "AS", "AT", "SO", "WE", "DO",
    "ME", "MY", "WHAT", "SHOW", "GIVE", "WANT", "FIND", "TELL", "LIST",
    "LAST", "LATEST", "CHECK", "LOOK", "NEED", "MAKE", "SHOULD",
    "WOULD", "COULD", "WILL", "FROM", "WITH", "THIS", "THAT", "THESE",
    "THOSE", "HAVE", "BEEN", "ALSO", "JUST", "MORE", "SOME", "THEY",
    "THEIR", "WERE", "WHEN", "THEN", "HERE", "THAN", "INTO", "OVER",
    "AFTER", "UNDER", "LIKE", "ONLY", "ABOUT", "HIGH", "LOW", "WEEK",
    "YEAR", "QUARTER", "ANNUAL", "MONTHLY", "QUARTERLY", "HISTORY",
    "REPORT", "DATA", "INFO", "RATIO", "PRICE", "VALUE",
    "CURRENT", "RECENT", "EPS", "LTP", "NAV", "BUY", "SELL", "STOCK",
    "MARKET", "TRADE", "SHARE", "DIVIDEND", "CORPORATE", "EVENT",
    "AGM", "PE", "DISPLAY", "FETCH", "PLEASE", "PDF", "CSV", "FILE",
    "HELLO", "HI", "HEY", "GOOD", "MORNING", "EVENING", "AFTERNOON",
    "HOW", "WHO", "WHY", "WHERE", "YES", "NO", "OK", "THANKS", "THANK",
    "FINBOT", "BOT", "ASSISTANT", "HELP",
}


def _extract_symbol(text: str) -> str | None:
    """
    Extract stock symbol from free text.
    First checks database for valid symbols (case-insensitive),
    then checks for user-typed ALL-CAPS words.
    """
    tokens = re.findall(r'\b[A-Za-z0-9&]{2,12}\b', text)
    for t in tokens:
        upper_t = t.upper()
        if upper_t not in _NOISE_WORDS and symbol_exists(upper_t):
            return upper_t

    caps = re.findall(r'\b[A-Z0-9&]{2,12}\b', text)
    for c in caps:
        if c not in _NOISE_WORDS and not c.isdigit():
            return c
    return None


def _detect_report_topic(sql: str) -> str:
    """Detect a concise, meaningful report label from the generated SQL."""
    sql_lower = sql.lower()
    if "financial_annual" in sql_lower:
        return "annual_eps"
    if "financial_quarterly" in sql_lower:
        return "quarterly_eps"
    if "dividend_history" in sql_lower:
        return "dividend_history"
    if "dividend_corp_action" in sql_lower:
        return "dividend_declarations"
    if "corporate_event" in sql_lower:
        return "corporate_events"
    if "basic_info" in sql_lower:
        return "fundamentals"
    return "financial_report"


# General-chat fallback
_GENERAL_SYSTEM_PROMPT = """\
You are finbot, a friendly financial data assistant for the Bangladesh DSE \
(Dhaka Stock Exchange) OMS system.

If the user asks about a specific stock symbol, remind them to include the DSE \
symbol (e.g. PTL, GP, RENATA). You can explain what data is available, greet \
the user, or answer general finance questions — but never invent specific stock \
numbers from your own knowledge.
"""


async def _general_reply(user_message: str) -> str:
    """LLM reply for messages that don't require a DB lookup."""
    prompt = f"{_GENERAL_SYSTEM_PROMPT}\n\nUSER: {user_message}\n\nfinbot:"
    try:
        return await ask_llm(prompt)
    except Exception as exc:
        return f"Sorry, I'm having trouble reaching the AI model right now. ({exc})"


# Main agent entry point
async def run_agent(user_message: str) -> dict:
    """
    Dynamic agent pipeline.

    Returns a structured dict (SQL is NEVER exposed to the client):
      { type, content, symbol, data_type, report_id, total_rows }
    """
    is_all = _is_all_symbols_request(user_message)
    symbol = None if is_all else _extract_symbol(user_message)
    wants_report = _wants_report(user_message)

    # If the user only says "report" or "download report" without a symbol and without detail:
    if wants_report and not symbol and not is_all and len(user_message.strip().split()) <= 3:
        return {
            "type": "text",
            "content": "Sure! Which stock symbol would you like the report for? (e.g. AOL, GP, PTL, RENATA) Or say 'all symbols' for a market-wide report.",
        }

    # Execute dynamic query generation
    result = await generate_and_execute(user_message)

    # 1. LLM said it cannot generate a SQL query → treat as general chat
    if result.cannot_generate:
        reply = await _general_reply(user_message)
        return {"type": "text", "content": reply}

    # 2. Something went wrong (schema fetch, LLM, DB error)
    if result.error:
        return {
            "type": "error",
            "content": f"⚠️ I ran into a problem: {result.error}",
        }

    # 3. Query returned no rows
    if not result.rows:
        return {
            "type": "text",
            "total_rows": 0,
            "content": (
                "No records were found for your query. "
                "Please double-check the symbol name or date range and try again."
            ),
        }

    # 4. Success — determine appropriate symbol identifier (NEVER pick a random row's symbol!)
    symbols_in_rows = {r.get("symbol") for r in result.rows if r.get("symbol")}
    if is_all or len(symbols_in_rows) > 1:
        final_symbol = "ALL"
    elif symbol:
        final_symbol = symbol
    elif len(symbols_in_rows) == 1:
        final_symbol = list(symbols_in_rows)[0]
    else:
        final_symbol = "ALL" if is_all else "REPORT"

    # Ask LLM to format a human-readable response using chunking
    response_prompt = _build_response_prompt(user_message, result.rows)
    try:
        answer = await ask_llm(response_prompt)
    except Exception as exc:
        answer = (
            f"⚠️ AI response formatting failed ({exc}). "
            f"Retrieved {len(result.rows)} records successfully."
        )

    # Success — cache rows and generate report_id for instant export
    report_id = uuid.uuid4().hex[:12]
    data_type = _detect_report_topic(result.sql)
    save_report_data(report_id, result.rows, symbol=final_symbol, data_type=data_type, sql=result.sql)

    # If the user asked for a report, return format picker
    if wants_report:
        return {
            "type": "ask_format",
            "content": answer,
            "symbol": final_symbol,
            "data_type": data_type,
            "report_id": report_id,
            "total_rows": len(result.rows),
        }

    return {
        "type": "text",
        "content": answer,
        "symbol": final_symbol,
        "report_id": report_id,
        "data_type": data_type,
        "total_rows": len(result.rows),
    }
