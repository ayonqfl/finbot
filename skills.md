# finbot — Project Skills & Build Reference

> **Bangladesh OMS Financial Analysis Chatbot**  
> Stack: FastAPI · Google Gemini API · PostgreSQL · Bootstrap 5 · jQuery  
> Author workspace: `g:\practice-codes\finbot`  
> DB URI: configured via `FINANCIAL_DB_URI` in `app/core/.env`

---

## 🎯 Core Goal

finbot is a **read-only, information-and-report chatbot** for the Bangladesh OMS trading system.

| ✅ What it DOES | ❌ What it NEVER does |
|---|---|
| Answers questions about financial data from PostgreSQL | Make buy/sell decisions |
| Retrieves LTP, dividend, EPS, PE, NAV etc. for any symbol | Execute trades |
| Generates PDF / CSV reports for any symbol on request | Recommend guaranteed investment strategies |
| Uses Gemini AI to give natural-language explanations | Provide financial advice as a licensed advisor |
| Streams AI responses via JSON (non-streaming chat endpoint) | Require any login or authentication |

**No login, no auth, no account system.** The app opens directly to the chat interface.

**Report workflow:** Before generating any report, the agent returns `type: ask_format` — the frontend shows [PDF] [CSV] inline buttons. User clicks to trigger `/export/`.

---

## 🤖 LLM Configuration

All Gemini settings are controlled via environment variables in `app/core/.env`.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Primary model |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.5-flash-lite` | Fallback on 404 / 429 / 503 |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` | API base URL |
| `ENABLE_MODEL_FALLBACK` | `true` | Auto-switch to fallback model on recoverable errors |

**To disable fallback** (fail fast on primary model errors): set `ENABLE_MODEL_FALLBACK=false` in `.env`.

**To change model at runtime**: edit `.env` and restart the server — no code changes needed.

> [!IMPORTANT]
> `langchain`, `langchain-community`, and `langchain-ollama` are still in `requirements.txt` but are **not actively used**. The app uses a direct Gemini HTTP client in `app/services/llm.py`.

---

## 📁 Project Structure

```
finbot/
│
├── app/                             # FastAPI application package
│   ├── __init__.py
│   ├── main.py                      # App entry point, router registration, CORS
│   │
│   ├── api/                         # Route handlers
│   │   ├── __init__.py
│   │   ├── chat.py                  # POST /chat/ → JSONResponse
│   │   └── export.py                # GET  /export/ → FileResponse (PDF/CSV)
│   │
│   ├── core/                        # Config & shared dependencies
│   │   ├── __init__.py
│   │   ├── .env                     # ← Environment variables (DB URI, Gemini settings)
│   │   ├── config.py                # Loads .env, exports all settings as constants
│   │   ├── database.py              # SQLAlchemy engine + schema fetcher
│   │   └── query_generator.py       # Dynamic SQL pipeline (LLM→SQL→Execute)
│   │
│   ├── services/                    # Business logic
│   │   ├── __init__.py
│   │   ├── agent.py                 # Intent detection & pipeline orchestration
│   │   ├── llm.py                   # Gemini HTTP client (ask_llm, check_llm)
│   │   ├── db_tools.py              # Only: symbol_exists() — static queries removed
│   │   └── report.py                # CSV (pandas) and PDF (ReportLab) generators
│   │
│   └── models/                      # Pydantic schemas
│       ├── __init__.py
│       └── financial.py             # ChatRequest, ChatResponse, etc.
│
├── frontend/
│   ├── index.html                   # Main chat UI (Bootstrap 5 dark theme)
│   ├── css/
│   │   └── styles.css               # Glassmorphism dark mode + animations
│   └── js/
│       └── chat.js                  # jQuery — JSON response handling, download buttons
│
├── sql/                             # Reference SQL / DDL (not executed at startup)
├── requirements.txt
├── skills.md
└── README.md
```

> [!NOTE]
> There is **no** `docker-compose.yml` or `Dockerfile` in the current project. No `config.py` at the project root either — all config lives in `app/core/config.py` + `app/core/.env`.

---

## 🗄️ Database Schema Reference

All tables live in the `stockdb` PostgreSQL database, schema `public`.  
Connection: configured via `FINANCIAL_DB_URI` in `app/core/.env`.

> [!TIP]
> The live schema is fetched automatically at startup by `get_stockdb_schema()` and cached in memory by `query_generator.py`. Query `GET /schema` to inspect it at runtime.

---

### Table: `basic_info`

Core fundamental data for each symbol (LTP, PE, NAV, market cap, etc.).

| Column | Type | Notes |
|---|---|---|
| `symbol` | varchar | Stock ticker (PK-like) |
| `yesterday_close` | numeric | Last Traded Price (LTP) |
| `wh52` | varchar | 52-week high |
| `wl52` | numeric | 52-week low |
| `p_e` | numeric | Price-to-Earnings ratio |
| `nav` | numeric | Net Asset Value |
| `dividend_yield` | varchar | Dividend yield % |
| `trailing_pe` | numeric | Trailing PE |
| `market_cap` | numeric | Market capitalisation |
| `paid_up_capital` | numeric | Paid-up capital |
| `authorized_capital` | numeric | Authorized capital |
| `total_share` | numeric | Total shares outstanding |
| `free_float` | numeric | Free float shares |
| `floor_price` | numeric | Exchange floor price |
| `block_floor_price` | numeric | Block market floor price |
| `short_term_loan` | numeric | Short-term loan |
| `long_term_loan` | numeric | Long-term loan |
| `reserve` | varchar | Reserve value |
| `year_end` | varchar | Fiscal year end (e.g. `31-Dec`) |
| `year_value` | varchar | Current fiscal year |
| `daily_nav` | varchar | Daily NAV |
| `daily_nav_date` | varchar | Date of daily NAV |
| `last_update` | varchar | Update timestamp |
| `last_ltp` | numeric | Most recent LTP (for intraday) |

**Common queries:**
```sql
-- LTP and key fundamentals
SELECT symbol, yesterday_close AS ltp, p_e, nav, dividend_yield, market_cap, trailing_pe
FROM public.basic_info WHERE symbol = 'PTL';

-- 52-week high/low
SELECT symbol, wh52, wl52 FROM public.basic_info WHERE symbol = 'GP';
```

> [!CAUTION]
> `dividend_yield`, `floor_price`, `p_e`, `nav`, `market_cap` all live in **`basic_info`** — NOT in `financial_annual`. Never query these from the wrong table.

---

### Table: `dividend_history`

Yearly dividend data per symbol.

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | varchar | Stock ticker |
| `year` | varchar | Fiscal year (e.g. `2025`) |
| `cash` | numeric | Cash dividend amount |
| `stock` | numeric | Stock dividend % |
| `yield_pct` | numeric | Dividend yield percentage |
| `rights` | numeric | Rights issue info (nullable) |
| `last_update` | varchar | Timestamp string |

**Common queries:**
```sql
-- Full dividend history for a symbol
SELECT year, cash, stock, yield_pct FROM public.dividend_history
WHERE symbol = 'PTL' ORDER BY year DESC;
```

---

### Table: `corporate_event`

Corporate events (EPS announcements, AGM dates, dividend declarations).

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | varchar | Stock ticker |
| `declaration_date` | varchar | Date of declaration (nullable) |
| `action_date` | varchar | Effective action date |
| `impact` | varchar | Impact level (`HIGH`, `MEDIUM`, etc.) |
| `news` | varchar | Event type (`DIVIDEND`, `FINAL EPS`, `Q1 EPS`, `Q2 EPS`) |
| `actual_value` | varchar | Actual announced value |
| `forecast_value` | varchar | Analyst forecast (nullable) |
| `previous_value` | varchar | Prior period value |
| `last_update` | timestamp with time zone | Record update timestamp |

**Common queries:**
```sql
SELECT action_date, news, actual_value, previous_value FROM public.corporate_event
WHERE symbol = 'RENATA' ORDER BY action_date DESC;
```

---

### Table: `dividend_corp_action`

Declared dividend + AGM/record date schedule per symbol.

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | varchar | Stock ticker |
| `declaration_date` | varchar | When dividend was declared |
| `dividend` | varchar | Dividend string e.g. `55%C`, `5%C \| 5%S` |
| `record_date` | varchar | Record date (DDMMYYYY format) |
| `agm_date` | varchar | AGM date (DDMMYYYY format) |
| `last_update` | varchar | Update timestamp string |

**Common queries:**
```sql
SELECT declaration_date, dividend, record_date, agm_date
FROM public.dividend_corp_action
WHERE symbol = 'RENATA' ORDER BY id DESC LIMIT 1;
```

---

### Table: `financial_annual`

Annual EPS data per symbol.

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | varchar | Stock ticker |
| `year_value` | varchar | Fiscal year (e.g. `2026`) |
| `eps` | numeric | Earnings Per Share |

**Common queries:**
```sql
SELECT year_value, eps FROM public.financial_annual
WHERE symbol = 'BNIPLC' ORDER BY year_value DESC;
```

---

### Table: `financial_quarterly`

Quarterly EPS data per symbol.

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | varchar | Stock ticker |
| `quarter_date` | varchar | Quarter end date (e.g. `30092026`) |
| `quarter` | varchar | Quarter label (`q1`, `q2`, `q3`, `q4`) |
| `eps` | numeric | Quarterly EPS |
| `last_updates` | varchar | Update timestamp |

**Common queries:**
```sql
SELECT quarter_date, quarter, eps FROM public.financial_quarterly
WHERE symbol = 'SAMORITA' ORDER BY quarter_date DESC;
```

---

## 🔄 Request / Response Flow

### Chat (`POST /chat/`)

```
User message
    ↓
agent.py → run_agent()
    ├─ _extract_symbol()   — DB-validated symbol lookup
    ├─ _wants_report()     — keyword detection
    │
    └─ generate_and_execute()   [query_generator.py]
           ├─ get_schema_cached()          — schema fetched once, cached in memory
           ├─ ask_llm(sql_prompt)          — Gemini generates SQL
           ├─ _extract_sql() + _validate_sql()
           ├─ execute_raw_sql()            — SQLAlchemy runs the query
           └─ retry once if DB error      — LLM given error to self-correct
    │
    ├─ cannot_generate → _general_reply() (Gemini general chat)
    ├─ error           → { type: "error", content, sql }
    ├─ no rows         → { type: "text", content: "No records..." }
    ├─ wants_report    → { type: "ask_format", symbol, sql, rows }
    └─ success         → { type: "text", content (LLM-formatted answer), sql, rows }
```

### Export (`GET /export/`)

```
Query params: symbol, fmt (pdf|csv), sql (optional), data_type (optional)
    ↓
export.py
    ├─ Validate: symbol not null/undefined, fmt is pdf|csv
    ├─ symbol_exists() check against basic_info
    ├─ If sql provided: validate_sql() → execute_raw_sql()
    ├─ If no sql: generate_and_execute(prompt)
    └─ generate_csv() or generate_pdf() → FileResponse
```

---

## ⚙️ Configuration (`app/core/config.py`)

```python
from pathlib import Path
from dotenv import load_dotenv

# Loads from app/core/.env — explicit path, not CWD-dependent
load_dotenv(dotenv_path=Path(__file__).with_name('.env'))

FINANCIAL_DB_URI      = os.getenv("FINANCIAL_DB_URI", "<fallback url>")
BASE_URL              = os.getenv("GEMINI_BASE_URL", "https://...")
GEMINI_API_KEY        = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL          = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
ENABLE_MODEL_FALLBACK = os.getenv("ENABLE_MODEL_FALLBACK", "true").lower() == "true"
PRIMARY_MODEL         = GEMINI_MODEL    # backward-compat alias
FALLBACK_MODEL        = GEMINI_FALLBACK_MODEL
REPORTS_DIR           = "reports"
APP_TITLE             = "finbot — OMS Financial Chatbot"
APP_VERSION           = "1.0.0"
```

> [!IMPORTANT]
> `load_dotenv()` without a path argument reads from the **current working directory** (where uvicorn is launched), **not** from the directory of `config.py`. Since `.env` lives inside `app/core/`, always use `Path(__file__).with_name('.env')` to load it correctly.

---

## ⚙️ Implementation Rules

1. **Symbol normalization** — always `.upper().strip()` before any DB query.
2. **Parameterized SQL** — use SQLAlchemy `text()` with `:sym` binding, never f-strings.
3. **PostgreSQL date syntax** — use `EXTRACT(YEAR FROM col)` or `DATE_PART('year', col)`, **never** `YEAR(col)` (MySQL syntax).
4. **Column accuracy** — always verify column belongs to that exact table from the live schema; never assume.
5. **Format-first rule** — agent returns `type: ask_format`; frontend shows buttons. Never auto-generate without user selecting format.
6. **Reports folder** — save generated files to `./reports/` directory; auto-created if missing.
7. **CORS** — allow all origins (`*`) — no auth required (R&D project).
8. **Static files** — frontend served via `StaticFiles` mount at `/static`; root `/` returns `index.html`.
9. **Error handling** — symbol not found → friendly message, not a stack trace.
10. **No buy/sell** — enforced in both SQL-generation system prompt and response-formatting system prompt.
11. **Schema caching** — `get_schema_cached()` fetches once per server lifetime; restart to refresh.
12. **LLM fallback** — controlled by `ENABLE_MODEL_FALLBACK`; triggers on HTTP 404 / 429 / 503 from Gemini.

---

## 🔧 Requirements

```
# Web framework
fastapi==0.115.0
uvicorn[standard]==0.30.0

# Database
sqlalchemy==2.0.35
psycopg2-binary==2.9.9

# Data & Reports
pandas==2.2.3
reportlab==4.2.2

# HTTP client (Gemini API)
httpx==0.27.2

# Utilities
python-dotenv==1.0.1

# Unused (kept for compatibility — may be removed)
langchain==0.3.0
langchain-community==0.3.0
langchain-ollama==0.2.0
```

---

## 🚀 Quick Start (Dev)

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
# Edit app/core/.env with your values:
#   FINANCIAL_DB_URI=postgresql+psycopg2://user:pass@host:port/stockdb
#   GEMINI_API_KEY=your_key_here
#   GEMINI_MODEL=gemini-3.1-flash-lite

# 3. Create reports output directory
mkdir reports

# 4. Start FastAPI dev server
uvicorn app.main:app --reload --port 8000
# OR if you prefer port 1100:
uvicorn app.main:app --reload --port 1100

# 5. Open browser
# http://localhost:8000
# http://localhost:8000/health   → DB + LLM status
# http://localhost:8000/schema   → Live DB schema dump
```

> [!TIP]
> Run **without `--reload`** during heavy LLM calls to avoid `CancelledError` from file-watcher interrupting long async requests (Gemini timeout is 90 s).

---

## ✅ File Status Checklist

| File | Status | Notes |
|---|---|---|
| `app/core/config.py` | ✅ Done | Loads `.env` from explicit path |
| `app/core/.env` | ✅ Done | DB URI + Gemini settings |
| `app/core/database.py` | ✅ Done | Engine + schema fetcher + guard against empty URI |
| `app/core/query_generator.py` | ✅ Done | Full LLM→SQL→Execute pipeline with retry |
| `app/services/llm.py` | ✅ Done | Gemini HTTP client, fallback, `ask_llm`, `check_llm` |
| `app/services/agent.py` | ✅ Done | Intent routing, report detection, symbol extraction |
| `app/services/db_tools.py` | ✅ Done | Only `symbol_exists()` remains (static queries removed) |
| `app/services/report.py` | ✅ Done | PDF (ReportLab) + CSV (pandas) generators |
| `app/models/financial.py` | ✅ Done | `ChatRequest` and other Pydantic schemas |
| `app/api/chat.py` | ✅ Done | `POST /chat/` → JSONResponse |
| `app/api/export.py` | ✅ Done | `GET /export/` → FileResponse with auto-query fallback |
| `app/main.py` | ✅ Done | Routers, CORS, StaticFiles, `/health`, `/schema` |
| `frontend/index.html` | ✅ Done | Bootstrap 5 dark theme chat UI |
| `frontend/css/styles.css` | ✅ Done | Glassmorphism + animations |
| `frontend/js/chat.js` | ✅ Done | JSON response handling + download button logic |
| `requirements.txt` | ✅ Done | All dependencies |

---

*finbot R&D Project — Bangladesh OMS | Last updated: 2026-11-09*
