# finbot - Dynamic SQL Query Generator
# Flow: user_message + db_schema -> LLM -> raw SQL -> sanitize -> execute -> rows

import re
import json
from decimal import Decimal
from datetime import date, datetime

from sqlalchemy import text

from app.core.database import engine, get_stockdb_schema
from app.services.llm import ask_llm

# Security: forbidden SQL keywords
_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE"
    r"|EXECUTE|EXEC|COPY|pg_read_file|pg_ls_dir|pg_stat_file)\b",
    re.IGNORECASE,
)

# Schema cache (defined before validator so get_allowed_tables() is available)

_schema_cache: dict | None = None


def get_schema_cached() -> dict:
    """
    Return DB schema dict (cached after first fetch).
    Keys are table names; values are lists of "column (type)" strings.
    Restart the server to force a schema refresh.
    """
    global _schema_cache
    if _schema_cache is None:
        try:
            _schema_cache = get_stockdb_schema()
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch DB schema: {exc}") from exc
    return _schema_cache


def get_allowed_tables() -> set[str]:
    """
    Return the set of table names that actually exist in the database.
    Derived dynamically from the live schema — no hardcoded list needed.
    """
    return set(get_schema_cached().keys())


# SQL generation prompt

_SQL_SYSTEM_PROMPT = """\
You are a PostgreSQL expert for a Bangladesh DSE (Dhaka Stock Exchange) financial database.

Your ONLY job is to write a single, safe, read-only SELECT query that answers the user's question.

RULES:
1. Output ONLY the raw SQL query — no markdown, no code fences, no explanation.
2. Always use the `public` schema prefix: e.g. `public.basic_info`.
3. Never use INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE, or any mutating statement.
4. NO LIMIT CLAUSE BY DEFAULT:
   - NEVER add a LIMIT clause unless the user explicitly requested a specific number of records (e.g. 'top 5', 'limit 10', 'highest 3').
   - Return all matching rows across the database.
5. SYMBOL FILTERING (CRITICAL):
   - SPECIFIC SYMBOL: If the user explicitly asks about a specific stock symbol (e.g. 'PTL', 'GP', 'AOL', 'RENATA'), filter strictly using `WHERE symbol = 'SYMBOL'` in UPPER-CASE.
   - ALL SYMBOLS / NO SYMBOL: If the user asks for 'all symbols', 'all stocks', 'entire market', 'all companies', or does NOT mention a specific stock ticker, DO NOT filter by symbol. NEVER invent, pick, or default to any arbitrary symbol (such as AAMRANET, GP, etc.). Query the requested data for ALL symbols across the market.
6. For cross-table queries, use JOINs on the `symbol` column.
7. Use meaningful column aliases so the result is human-readable.
8. If the question cannot be answered with a SELECT query or is unrelated to finance, output exactly: CANNOT_GENERATE
9. For date/time ordering, prefer DESC so the most recent data appears first.

CRITICAL — COLUMN ACCURACY (read carefully):
- Before using ANY column, verify it exists in that exact table from the DATABASE SCHEMA provided.
- NEVER guess or assume a column exists. If a column is not listed for a table, do not use it.
- If data spans multiple tables (e.g. dividend_yield is in basic_info, dividend history is in dividend_history),
  use a JOIN rather than looking for it in the wrong table.
- Common mistakes to AVOID:
    * dividend_yield, floor_price, p_e, nav, market_cap → they live in basic_info, NOT financial_annual
    * annual EPS, revenue, net_income → financial_annual or financial_quarterly
    * cash/stock dividend per year → dividend_history
    * agm_date, record_date, declaration_date → dividend_corp_action

CRITICAL — POSTGRESQL SYNTAX & DATE FILTERING:
- Date extraction: EXTRACT(YEAR FROM column) or DATE_PART('year', column) — NOT YEAR(column)
- Current date: CURRENT_DATE — NOT NOW() for date-only comparisons
- String year columns (e.g. year_value or year as character varying): filter with = '2023' or cast to integer
- When user asks for "last N years" / "latest N records" (e.g. "last 2 years of dividends", "last 3 years EPS"):
  Sort descending and limit: `ORDER BY year DESC LIMIT N` (or `LIMIT 2` for last 2 years), because historical stock records in the database might not include the present calendar year.
"""


def _build_sql_prompt(user_message: str, schema: dict) -> str:
    """Build the full prompt sent to LLM for SQL generation."""
    schema_text = json.dumps(schema, indent=2)
    return (
        f"{_SQL_SYSTEM_PROMPT}\n\n"
        f"DATABASE SCHEMA:\n{schema_text}\n\n"
        f"USER QUESTION: {user_message}\n\n"
        f"SQL QUERY:"
    )


def _build_retry_prompt(user_message: str, schema: dict, bad_sql: str, db_error: str) -> str:
    """
    Build a correction prompt when the first SQL attempt failed at execution.
    Sends the broken SQL + DB error message back to the LLM to self-correct.
    """
    schema_text = json.dumps(schema, indent=2)
    return (
        f"{_SQL_SYSTEM_PROMPT}\n\n"
        f"DATABASE SCHEMA:\n{schema_text}\n\n"
        f"USER QUESTION: {user_message}\n\n"
        f"Your previous SQL attempt FAILED with this database error:\n"
        f"  {db_error}\n\n"
        f"Broken SQL was:\n{bad_sql}\n\n"
        f"Write a CORRECTED SQL query. Output ONLY the fixed SQL, nothing else.\n\n"
        f"CORRECTED SQL QUERY:"
    )


# SQL sanitizer
def _extract_sql(raw: str) -> str:
    """
    Strip markdown code fences and stray prose from the LLM output.
    Returns the clean SQL string.
    """
    # Remove ```sql ... ``` or ``` ... ``` fences
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).strip("` \n\r\t")
    # Take only the first statement (up to and including the first semicolon)
    # to guard against multi-statement injection
    if ";" in raw:
        raw = raw[: raw.index(";") + 1]
    return raw.strip()


def _validate_sql(sql: str) -> tuple[bool, str]:
    """
    Validate that the SQL is safe to run.
    - Blocks any mutating / dangerous keywords.
    - Ensures it is a SELECT statement.
    - Verifies every table referenced actually exists in the live DB schema.
    Returns (ok: bool, reason: str).
    """
    if not sql or sql.upper() == "CANNOT_GENERATE":
        return False, "LLM indicated it cannot generate a query for this request."

    if _FORBIDDEN_PATTERN.search(sql):
        return False, "Query contains a forbidden keyword (mutating or dangerous SQL)."

    if not re.search(r"\bSELECT\b", sql, re.IGNORECASE):
        return False, "Query does not contain a SELECT statement."

    # Verify every referenced table actually exists in the live DB schema.
    # Pattern handles both: FROM public.basic_info  AND  FROM basic_info
    # Clean out EXTRACT(... FROM ...) and SUBSTRING(... FROM ...) to avoid false matches on function keywords
    clean_sql = re.sub(r'\bEXTRACT\s*\([^)]*\)', '', sql, flags=re.IGNORECASE)
    clean_sql = re.sub(r'\bSUBSTRING\s*\([^)]*\)', '', clean_sql, flags=re.IGNORECASE)
    allowed = get_allowed_tables()
    referenced = re.findall(
        r'(?:FROM|JOIN)\s+(?:public\.)?(\w+)',
        clean_sql,
        re.IGNORECASE,
    )
    for table in referenced:
        if table and table.lower() not in allowed:
            return False, f"Query references unknown table '{table}'."

    return True, ""


# Query executor

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


def execute_raw_sql(sql: str) -> tuple[list[dict], str | None]:
    """
    Execute a validated SELECT query.
    Returns (rows: list[dict], error: str | None).
    On success, error is None.
    On failure, rows is [] and error contains the message.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = _rows_to_dicts(result)
            return rows, None
    except Exception as exc:
        return [], f"Database error: {exc}"


# Main public function

# Public alias so external modules (e.g. export.py) can call validate_sql()
# without reaching into the private _validate_sql name.
validate_sql = _validate_sql

class QueryResult:
    """Container returned by generate_and_execute."""

    __slots__ = ("sql", "rows", "error", "cannot_generate", "total_rows")

    def __init__(
        self,
        sql: str = "",
        rows: list[dict] | None = None,
        error: str | None = None,
        cannot_generate: bool = False,
        total_rows: int = 0,
    ):
        self.sql = sql
        self.rows = rows or []
        self.error = error
        self.cannot_generate = cannot_generate
        self.total_rows = total_rows

    @property
    def ok(self) -> bool:
        return not self.error and not self.cannot_generate


async def generate_and_execute(user_message: str) -> QueryResult:
    """
    Full pipeline:
      1. Fetch schema (cached)
      2. Ask LLM to write a SQL query
      3. Extract & validate SQL
      4. Execute — if DB error, retry once with the error fed back to LLM
      5. Return QueryResult
    """
    # Step 1 — schema
    try:
        schema = get_schema_cached()
    except RuntimeError as exc:
        return QueryResult(error=str(exc))

    # Step 2 — LLM generates SQL
    prompt = _build_sql_prompt(user_message, schema)
    try:
        raw_response = await ask_llm(prompt)
    except Exception as exc:
        return QueryResult(error=f"LLM request failed: {exc}")

    # Step 3 — extract & validate
    sql = _extract_sql(raw_response)

    if sql.upper().strip().rstrip(";") == "CANNOT_GENERATE":
        return QueryResult(cannot_generate=True)

    ok, reason = _validate_sql(sql)
    if not ok:
        return QueryResult(sql=sql, error=reason)

    # Debug: print the generated SQL (server-side only — never sent to the client)
    print(f"[QueryGen] Generated SQL:\n{sql}")

    # Step 4 — execute (with one auto-retry on DB error)
    rows, db_error = execute_raw_sql(sql)
    if db_error:
        print(f"[QueryGen] First SQL attempt failed: {db_error}\nSQL: {sql}\nRetrying...")
        retry_prompt = _build_retry_prompt(user_message, schema, sql, db_error)
        try:
            raw_retry = await ask_llm(retry_prompt)
        except Exception as exc:
            return QueryResult(sql=sql, error=db_error)  # return original error

        retry_sql = _extract_sql(raw_retry)

        if retry_sql.upper().strip().rstrip(";") == "CANNOT_GENERATE":
            return QueryResult(sql=sql, error=db_error)

        ok2, reason2 = _validate_sql(retry_sql)
        if not ok2:
            return QueryResult(sql=retry_sql, error=reason2)

        print(f"[QueryGen] Retry SQL:\n{retry_sql}")
        rows, db_error2 = execute_raw_sql(retry_sql)
        if db_error2:
            # Both attempts failed — return the retry SQL and its error
            return QueryResult(sql=retry_sql, error=db_error2)

        total = len(rows)
        print(f"[QueryGen] Retry succeeded: {total} rows returned")
        return QueryResult(sql=retry_sql, rows=rows, total_rows=total)

    total = len(rows)
    print(f"[QueryGen] Success: {total} rows returned")
    return QueryResult(sql=sql, rows=rows, total_rows=total)
