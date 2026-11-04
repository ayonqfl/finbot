#  finbot — Agent (Dynamic SQL Pipeline)
#  Flow: user message → SQL generator → DB execute → LLM response formatter

import json
import re

from app.core.query_generator import generate_and_execute
from app.services.llm import ask_llm
from app.services.db_tools import symbol_exists

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
"""


def _build_response_prompt(user_message: str, sql: str, rows: list[dict]) -> str:
    """Build the prompt that asks the LLM to narrate the query result."""
    data_json = json.dumps(rows, default=str, indent=2)
    row_count = len(rows)
    return (
        f"{_RESPONSE_SYSTEM_PROMPT}\n\n"
        f"USER QUESTION: {user_message}\n\n"
        f"SQL EXECUTED:\n{sql}\n\n"
        f"RESULT ({row_count} row{'s' if row_count != 1 else ''}):\n{data_json}\n\n"
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


# Symbol extractor (kept for report-intent path)
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
    # 1. Check all tokens case-insensitively against database symbols
    tokens = re.findall(r'\b[A-Za-z0-9&]{2,12}\b', text)
    for t in tokens:
        upper_t = t.upper()
        if upper_t not in _NOISE_WORDS and symbol_exists(upper_t):
            return upper_t

    # 2. Check for tokens specifically typed in ALL-CAPS by the user
    caps = re.findall(r'\b[A-Z0-9&]{2,12}\b', text)
    for c in caps:
        if c not in _NOISE_WORDS and not c.isdigit():
            return c
    return None


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

    Returns a structured dict:
      { type, content, sql, rows, symbol, error, data_type }
    """
    symbol = _extract_symbol(user_message)
    wants_report = _wants_report(user_message)

    # If the user only says "report" or "download report" without a symbol and without detail:
    if wants_report and not symbol and len(user_message.strip().split()) <= 3:
        return {
            "type": "text",
            "content": "Sure! Which stock symbol would you like the report for? (e.g. AOL, GP, PTL, RENATA)",
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
            "sql": result.sql or None,
        }

    # 3. Query returned no rows
    if not result.rows:
        return {
            "type": "text",
            "sql": result.sql,
            "rows": [],
            "content": (
                "No records were found for your query. "
                "Please double-check the symbol name or date range and try again.\n\n"
                f"**SQL executed:**\n```sql\n{result.sql}\n```"
            ),
        }

    # 4. Success — ask LLM to format a human-readable response
    response_prompt = _build_response_prompt(user_message, result.sql, result.rows)
    try:
        answer = await ask_llm(response_prompt)
    except Exception as exc:
        answer = (
            f"⚠️ AI response formatting failed ({exc}). "
            "Here is the raw data:"
        )

    # Deduce symbol if not already extracted
    final_symbol = symbol or (result.rows[0].get("symbol") if result.rows else "STOCK")

    # If the user asked for a report, provide the report in chat AND format picker buttons
    if wants_report:
        return {
            "type": "ask_format",
            "content": answer,
            "symbol": final_symbol,
            "data_type": "report",
            "sql": result.sql,
            "rows": result.rows,
        }

    return {
        "type": "text",
        "content": answer,
        "symbol": final_symbol,
        "sql": result.sql,
        "rows": result.rows,
    }
