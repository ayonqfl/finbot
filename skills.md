# finbot — Project Skills & Build Reference

> **Bangladesh OMS Financial Analysis Chatbot**  
> Stack: FastAPI · LangChain · Ollama · PostgreSQL · Bootstrap 5 · jQuery  
> Author workspace: `g:\practice-codes\finbot`  
> DB URI: `postgresql+psycopg2://stockdata:pass4321@192.168.155.22:5446/stockdb`

---

## 🎯 Core Goal (Single Source of Truth)

finbot is a **read-only, information-and-report chatbot** for the Bangladesh OMS trading system.

| ✅ What it DOES | ❌ What it NEVER does |
|---|---|
| Answers questions about financial data from PostgreSQL | Make buy/sell decisions and No auth implementation |
| Retrieves LTP, dividend, EPS, PE, NAV etc. for any symbol | Execute trades |
| Generates PDF / CSV reports for any symbol on request | Recommend guaranteed investment strategies |
| Uses LLM to give natural-language explanations & suggestions | Provide financial advice as a licensed advisor |

**No login, no auth, no account system.** The app opens directly to the chat interface — user lands and starts chatting immediately. Zero friction.

**Report workflow rule:** Before generating any report, the agent **must ask the user which format they want** (PDF or CSV).

---

## 🤖 LLM Model Selection

You have two models locally on Ollama:

| Model | Size | Best for finbot? |
|---|---|---|
| `deepseek-r1:latest` | 5.2 GB | ⭐ **Recommended** — Strong reasoning, better at structured thinking, handles finance terminology well, step-by-step analysis |
| `llama3.2:latest` | 2.0 GB | Good fallback — Lighter, faster responses, but less reasoning depth |

**Recommendation: Use `deepseek-r1:latest`** as the primary model.

- deepseek-r1 has explicit chain-of-thought reasoning (`<think>` tags) which helps the LangChain agent correctly parse user intent (e.g. "Give me PTL dividend history as PDF" → correctly identifies symbol=PTL, data=dividend_history, format=PDF).
- llama3.2 can be used as a fallback or for simple greeting/clarification messages (faster).

**Ollama config in code:**
```python
OLLAMA_BASE_URL = "http://localhost:11434"
PRIMARY_MODEL   = "deepseek-r1:latest"
FALLBACK_MODEL  = "llama3.2:latest"
```

---

## 📁 Project Structure

```
finbot/
│
├── app/                          # FastAPI application package
│   ├── __init__.py
│   ├── main.py                   # App entry point, router registration, CORS
│   │
│   ├── api/                      # Route handlers
│   │   ├── __init__.py
│   │   ├── chat.py               # POST /chat  → SSE streaming response
│   │   └── export.py             # GET  /export → FileResponse (PDF/CSV)
│   │
│   ├── core/                     # Config & shared dependencies
│   │   ├── __init__.py
│   │   ├── config.py             # Settings (DB URI, Ollama URL, model names)
│   │   └── database.py           # SQLAlchemy engine + session factory
│   │
│   ├── services/                 # Business logic
│   │   ├── __init__.py
│   │   ├── agent.py              # LangChain agent — intent detection & tool routing
│   │   ├── llm.py                # Ollama LLM wrapper (LangChain ChatOllama)
│   │   ├── db_tools.py           # SQL query functions (one per table/use-case)
│   │   └── report.py             # CSV (pandas) and PDF (ReportLab) generators
│   │
│   └── models/                   # Pydantic schemas
│       ├── __init__.py
│       ├── chat.py               # ChatRequest, ChatResponse
│       └── financial.py          # Symbol, DividendRecord, BasicInfo, etc.
│
├── frontend/
│   ├── index.html                # Main chat UI (Bootstrap 5 dark theme)
│   ├── css/
│   │   └─ styles.css            # Custom styles — glassmorphism, dark mode, animations
│   └── js/
│       └─ chat.js               # jQuery — SSE handling, download button logic
│
├── sql/
│   └── schema_reference.sql      # Reference DDL based on real table structures
│
├── config.py                     # YOUR EXISTING FILE (DB URI)
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 🗄️ Database Schema Reference

All tables live in the `stockdb` database, schema `public`.  
**DB URI:** `postgresql+psycopg2://stockdata:pass4321@192.168.155.22:5446/stockdb`

---

### Table 1: `dividend_history`

Stores yearly dividend data per symbol.

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | character varying | Stock ticker (e.g. `PTL`, `GP`) |
| `last_update` | character varying | Timestamp string |
| `year` | character varying | Fiscal year (e.g. `2025`) |
| `cash` | numeric | Cash dividend amount |
| `stock` | numeric | Stock dividend % |
| `yield_pct` | numeric | Dividend yield percentage |
| `rights` | numeric | Rights issue info (nullable) |

**Sample data:**
```
id=1,  symbol=PTL, year=2025, cash=12.0, stock=0.0,  yield_pct=2.96
id=2,  symbol=PTL, year=2024, cash=5.0,  stock=10.0, yield_pct=0.7
id=3,  symbol=PTL, year=2023, cash=10.0, stock=0.0,  yield_pct=1.3
id=26, symbol=GP,  year=2025, cash=215.0,stock=0.0,  yield_pct=8.34
id=27, symbol=GP,  year=2024, cash=330.0,stock=0.0,  yield_pct=10.21
```

**Common queries:**
```sql
-- Full dividend history for a symbol
SELECT year, cash, stock, yield_pct FROM public.dividend_history
WHERE symbol = 'PTL' ORDER BY year DESC;

-- Latest dividend yield
SELECT yield_pct FROM public.dividend_history
WHERE symbol = 'PTL' ORDER BY year DESC LIMIT 1;
```

---

### Table 2: `corporate_event`

Corporate events (dividends declared, EPS announcements, AGM dates).

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | character varying | Stock ticker |
| `declaration_date` | character varying | Date of declaration (nullable) |
| `action_date` | character varying | Effective action date |
| `impact` | character varying | Impact level (`HIGH`, `MEDIUM`, etc.) |
| `news` | character varying | Event type (`DIVIDEND`, `FINAL EPS`, `Q1 EPS`, `Q2 EPS`) |
| `actual_value` | character varying | Actual announced value |
| `forecast_value` | character varying | Analyst forecast (nullable) |
| `previous_value` | character varying | Prior period value |
| `last_update` | timestamp with time zone | Record update timestamp |

**Sample data:**
```
id=5899, symbol=KAY&QUE,  action_date=2026-10-27, news=DIVIDEND,  actual_value=5%C | 5%S
id=5898, symbol=KAY&QUE,  action_date=2026-10-27, news=FINAL EPS, actual_value=11.25, forecast=9.49
id=5897, symbol=BSRMLTD,  action_date=2026-10-15, news=FINAL EPS, actual_value=14.48
id=5891, symbol=WALTONHIL,action_date=2026-08-29, news=DIVIDEND,  actual_value=175%C | 10%S
```

**Common queries:**
```sql
-- All events for a symbol
SELECT action_date, news, actual_value, previous_value FROM public.corporate_event
WHERE symbol = 'KAY&QUE' ORDER BY action_date DESC;
```

---

### Table 3: `dividend_corp_action`

Declared dividend + AGM schedule per symbol.

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | character varying | Stock ticker |
| `declaration_date` | character varying | When dividend was declared |
| `dividend` | character varying | Dividend string e.g. `55%C`, `5%C | 5%S` |
| `record_date` | character varying | Record date (DDMMYYYY format) |
| `last_update` | character varying | Update timestamp string |
| `agm_date` | character varying | AGM date (DDMMYYYY format) |

**Sample data:**
```
id=2688, symbol=KAY&QUE,   dividend=5%C | 5%S, record_date=17112026, agm_date=20261210
id=2686, symbol=RENATA,    dividend=55%C,      record_date=15112026, agm_date=20261219
id=2682, symbol=BSRMSTEEL, dividend=60.00%C,   record_date=15112026, agm_date=20261217
id=2680, symbol=BSRMLTD,   dividend=55%C,      record_date=15112026, agm_date=20261217
```

**Common queries:**
```sql
-- Latest dividend declaration for a symbol
SELECT declaration_date, dividend, record_date, agm_date
FROM public.dividend_corp_action
WHERE symbol = 'RENATA' ORDER BY id DESC LIMIT 1;
```

---

### Table 4: `basic_info`

Core fundamental data for each symbol (LTP, PE, NAV, market cap, etc.).

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | character varying | Stock ticker |
| `yesterday_close` | numeric | Last traded price (LTP) |
| `wh52` | character varying | 52-week high |
| `wl52` | numeric | 52-week low |
| `p_e` | numeric | Price-to-Earnings ratio |
| `reserve` | character varying | Reserve value |
| `nav` | numeric | Net Asset Value |
| `dividend_yield` | character varying | Dividend yield % |
| `year_end` | character varying | Fiscal year end (e.g. `31-Dec`) |
| `year_value` | character varying | Current fiscal year |
| `free_float` | numeric | Free float shares |
| `total_share` | numeric | Total shares outstanding |
| `market_cap` | numeric | Market capitalisation |
| `paid_up_capital` | numeric | Paid-up capital |
| `authorized_capital` | numeric | Authorized capital |
| `last_update` | character varying | Update timestamp |
| `floor_price` | numeric | Exchange floor price |
| `block_floor_price` | numeric | Block market floor price |
| `short_term_loan` | numeric | Short-term loan |
| `long_term_loan` | numeric | Long-term loan |
| `trailing_pe` | numeric | Trailing PE |
| `daily_nav` | character varying | Daily NAV |
| `daily_nav_date` | character varying | Date of daily NAV |

**Sample data:**
```
symbol=BNIPLC, yesterday_close=940.7, wh52=31.26, p_e=4.92,
total_share=44250000, market_cap=7447275000, paid_up_capital=442.5,
year_end=31-Dec, year_value=2025, last_update=26/10/2026-11:02:51 PM
```

**Common queries:**
```sql
-- LTP and key fundamentals for a symbol
SELECT symbol, yesterday_close AS ltp, p_e, nav, dividend_yield, market_cap, trailing_pe
FROM public.basic_info WHERE symbol = 'PTL';

-- 52-week high/low
SELECT symbol, wh52, wl52 FROM public.basic_info WHERE symbol = 'GP';
```

---

### Table 5: `financial_annual`

Annual EPS data per symbol.

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | character varying | Stock ticker |
| `year_value` | character varying | Fiscal year (e.g. `2026`) |
| `eps` | numeric | Earnings Per Share |

**Sample data:**
```
id=4000, symbol=KAY&QUE, year_value=2026, eps=11.25
id=3999, symbol=BNIPLC,  year_value=2025, eps=4.81
id=3998, symbol=BNIPLC,  year_value=2024, eps=4.19
id=3991, symbol=RENATA,  year_value=2026, eps=31.76
```

**Common queries:**
```sql
-- EPS history for a symbol
SELECT year_value, eps FROM public.financial_annual
WHERE symbol = 'BNIPLC' ORDER BY year_value DESC;
```

---

### Table 6: `financial_quarterly`

Quarterly EPS data per symbol.

| Column | Type | Notes |
|---|---|---|
| `id` | integer (PK) | Auto-increment |
| `symbol` | character varying | Stock ticker |
| `quarter_date` | character varying | Quarter end date (e.g. `30092026`) |
| `quarter` | character varying | Quarter label (`q1`, `q2`, `q3`, `q4`) |
| `eps` | numeric | Quarterly EPS |
| `last_updates` | character varying | Update timestamp |

**Sample data:**
```
id=6710, symbol=SAMORITA, quarter_date=30092026, quarter=q1, eps=0.83
```

**Common queries:**
```sql
-- All quarterly EPS for a symbol
SELECT quarter_date, quarter, eps FROM public.financial_quarterly
WHERE symbol = 'SAMORITA' ORDER BY quarter_date DESC;
```

---

## 🔧 Requirements

```
# requirements.txt

# Web framework
fastapi==0.115.0
uvicorn[standard]==0.30.0

# LLM & Agent
langchain==0.3.0
langchain-community==0.3.0
langchain-ollama==0.2.0

# Database
sqlalchemy==2.0.35
psycopg2-binary==2.9.9

# Data & Reports
pandas==2.2.3
reportlab==4.2.2

# Utilities
python-dotenv==1.0.1
sse-starlette==2.1.3
httpx==0.27.2
```

---

## 🚀 Phase-by-Phase Build Plan

### Phase 1 — Project Skeleton

**Goal:** FastAPI runs, DB connects, Ollama responds.

Steps:
1. Create all folders from the project structure above.
2. Copy `config.py` into `app/core/config.py` and add Ollama settings.
3. Create `app/core/database.py` — SQLAlchemy engine using the DB URI.
4. Create `app/main.py` — bare FastAPI app with `/health` endpoint.
5. Run: `uvicorn app.main:app --reload --port 8000`
6. Test DB: `GET /health` returns `{"db": "ok", "ollama": "ok"}`.

---

### Phase 2 — DB Query Tools

**Goal:** Python functions that query each financial table and return clean data.

Create `app/services/db_tools.py` with these functions:

```python
get_ltp(symbol)                  # → basic_info.yesterday_close
get_fundamentals(symbol)         # → p_e, nav, dividend_yield, market_cap, trailing_pe
get_dividend_history(symbol)     # → dividend_history rows
get_annual_eps(symbol)           # → financial_annual rows
get_quarterly_eps(symbol)        # → financial_quarterly rows
get_corporate_events(symbol)     # → corporate_event rows
get_dividend_declaration(symbol) # → dividend_corp_action rows
```

Rules:
- Takes `symbol: str` parameter — always `.upper().strip()` normalize before SQL.
- Returns `list[dict]` or `dict` (JSON-serialisable).
- Handles "symbol not found" gracefully → returns empty list / None.
- Uses **parameterized queries only** — never f-string SQL.

---

### Phase 3 — LangChain Agent

**Goal:** Agent understands user intent and calls the right DB tool.

Tool routing:
```
User message
    ↓
LangChain Agent (deepseek-r1 via Ollama)
    ↓ detects intent
Tool: get_ltp / get_fundamentals / get_dividend_history / ...
Tool: ask_format         →  "PDF or CSV?" (only when report requested)
Tool: generate_report    →  report.py (after format confirmed)
    ↓
Natural-language answer streamed back via SSE
```

**Core system prompt:**
```
You are finbot, a financial data assistant for the Bangladesh OMS trading system.
You ONLY answer questions using data from the PostgreSQL database.
You NEVER recommend buying or selling any stock.
You CAN explain financial metrics, show trends, compare years, and generate reports.
When a user asks for a report (PDF or CSV), ALWAYS ask which format they prefer first.
Available data: LTP, PE, NAV, dividend history, EPS (annual/quarterly), corporate events.
Symbol names are Bangladesh DSE-listed tickers (e.g. PTL, GP, BNIPLC, RENATA).
```

---

### Phase 4 — Report Generator

**Goal:** Generate clean PDF and CSV reports on demand.

```python
# app/services/report.py

def generate_csv(data: list[dict], symbol: str, report_type: str) -> str:
    """Returns file path of generated CSV."""
    df = pd.DataFrame(data)
    path = f"./reports/finbot_{symbol}_{report_type}.csv"
    df.to_csv(path, index=False)
    return path

def generate_pdf(data: list[dict], symbol: str, report_type: str) -> str:
    """Returns file path of generated PDF using ReportLab."""
    # Title bar, symbol name, date, clean data table
    path = f"./reports/finbot_{symbol}_{report_type}.pdf"
    # ReportLab canvas code here
    return path
```

---

### Phase 5 — FastAPI Endpoints

**Two endpoints only:**

#### `POST /chat`
```json
// Request
{ "message": "What is the LTP of PTL?" }

// Response (SSE stream)
data: {"token": "The"}
data: {"token": " last"}
data: {"token": " traded price of PTL is 405.20 BDT."}
data: [DONE]
```

#### `GET /export`
```
Query params: ?symbol=PTL&type=dividend_history&format=pdf
Response:     FileResponse — application/pdf or text/csv
              Content-Disposition: attachment; filename=finbot_PTL_dividend_history.pdf
```

---

### Phase 6 — Frontend UI

**Goal:** Premium dark-mode chat UI with inline PDF/CSV selection and download buttons.

Chat UI wireframe:
```
┌──────────────────────────────────────────────────────┐
│  🤖 finbot   Bangladesh Financial Chatbot            │  ← Glassmorphism header
├──────────────────────────────────────────────────────┤
│                                                      │
│  [Bot] Hello! Ask me about any DSE stock symbol...   │
│                                                      │
│  [User] Give me PTL dividend history                 │
│                                                      │
│  [Bot] I can prepare that report! Which format       │
│        would you like?  [📄 PDF]  [📊 CSV]           │
│                                                      │
│  [User] PDF please                                   │
│                                                      │
│  [Bot] ✅ Your PTL dividend report is ready!         │
│        [⬇ Download PDF]                              │
│                                                      │
├──────────────────────────────────────────────────────┤
│  💬 Ask anything about DSE stocks...    [Send ➤]     │  ← Input bar
└──────────────────────────────────────────────────────┘
```

Key behaviours:
- SSE tokens stream as typewriter effect.
- Agent returns `{"type": "ask_format", "symbol": "PTL"}` → show [PDF] [CSV] inline buttons.
- Agent returns `{"type": "report_ready", "url": "/export?..."}` → show [Download] button.
- Auto-scroll to newest message.
- Bootstrap 5 responsive grid.
- Dark glassmorphism theme with subtle gradient animations.

---

### Phase 7 — Testing

Test against these 10 queries end-to-end:

| # | User Message | Expected |
|---|---|---|
| 1 | "What is the LTP of PTL?" | Returns yesterday_close from basic_info |
| 2 | "Show GP dividend history" | Returns dividend_history rows for GP |
| 3 | "What is BNIPLC PE ratio?" | Returns basic_info.p_e |
| 4 | "Give me RENATA annual EPS" | Returns financial_annual rows |
| 5 | "I want PTL dividend report" | Asks: PDF or CSV? |
| 6 | "PDF please" (after #5) | Generates PDF, returns download link |
| 7 | "Latest corporate events for WALTONHIL?" | Returns corporate_event rows |
| 8 | "What is GP 52-week high?" | Returns basic_info.wh52 |
| 9 | "Show SAMORITA quarterly EPS" | Returns financial_quarterly rows |
| 10 | "Should I buy PTL?" | Declines buy/sell, offers factual data instead |

---

## ⚙️ Implementation Rules

1. **Symbol normalization** — always `.upper().strip()` before any DB query.
2. **Parameterized SQL** — use SQLAlchemy `text()` with `:symbol` binding, never f-strings.
3. **Format-first rule** — agent must ask format (PDF/CSV) before generating any report.
4. **Streaming via SSE** — use `sse-starlette` library; yield tokens as Ollama produces them.
5. **No buy/sell** — enforced in system prompt; agent politely declines and offers info.
6. **Reports folder** — save generated files to `./reports/` directory, auto-create if missing.
7. **CORS** — allow all origins (`*`) — no auth required (R&D project).
8. **Static files** — serve frontend via FastAPI `StaticFiles` mount at `/` so one server only.
9. **Error handling** — if symbol not found, return friendly message, not a stack trace.
10. **think tags** — strip `<think>...</think>` from deepseek-r1 output before sending to user.

---

## 🐳 Docker Compose (Reference)

```yaml
version: '3.9'
services:
  finbot:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FINANCIAL_DB_URI=postgresql+psycopg2://stockdata:pass4321@192.168.155.22:5446/stockdb
      - OLLAMA_BASE_URL=http://localhost:11434
    volumes:
      - ./reports:/app/reports

  # PostgreSQL is on 192.168.155.22:5446 (external — no container needed)
  # Ollama runs on host machine — no container needed for dev
```

---

## 📦 Quick Start (Dev — No Docker)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Make sure Ollama is running with the right model
ollama serve
ollama pull deepseek-r1:latest

# 3. Create reports output directory
mkdir reports

# 4. Start FastAPI dev server
uvicorn app.main:app --reload --port 8000

# 5. Open browser at
# http://localhost:8000
```

---

## 🗺️ Build Order Checklist

```
[ ] app/core/config.py          ← DB URI + Ollama settings
[ ] app/core/database.py        ← SQLAlchemy engine
[ ] app/services/db_tools.py    ← 7 query functions for all 6 tables
[ ] app/services/llm.py         ← Ollama / ChatOllama wrapper
[ ] app/services/agent.py       ← LangChain agent + tools registration
[ ] app/services/report.py      ← PDF (ReportLab) + CSV (pandas) generators
[ ] app/models/chat.py          ← Pydantic: ChatRequest, ChatResponse
[ ] app/models/financial.py     ← Pydantic: SymbolData, DividendRecord, etc.
[ ] app/api/chat.py             ← POST /chat SSE streaming endpoint
[ ] app/api/export.py           ← GET /export FileResponse endpoint
[ ] app/main.py                 ← Assemble routers, CORS, StaticFiles
[ ] frontend/index.html         ← Chat UI (Bootstrap 5 dark)
[ ] frontend/css/styles.css     ← Glassmorphism + animations
[ ] frontend/js/chat.js         ← SSE handling + download button logic
[ ] requirements.txt            ← All dependencies pinned
[ ] README.md                   ← Setup & usage instructions
```

---

*finbot R&D Project — Bangladesh OMS | Last updated: 2026-10-28*
