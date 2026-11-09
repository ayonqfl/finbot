# 🤖 finbot — Bangladesh Financial Assistant

> **AI-Powered Financial Data & Report Chatbot for the Bangladesh OMS Trading System**  
> Built with FastAPI, PostgreSQL, Ollama (DeepSeek-R1 / LLaMA 3.2), ReportLab, and Bootstrap 5.

---

## 📌 Overview

**finbot** is a zero-friction, read-only financial assistant designed for traders, analysts, and investors looking for quick fundamental data, historical performance metrics, corporate actions, and exportable reports on stocks listed on the **Dhaka Stock Exchange (DSE)**.

Users land directly into the chat interface without login barriers, ask plain-English questions, and can generate styled PDF or CSV reports on demand.

---

## 🎯 Core Features

- **⚡ Instant Fundamental Queries**: Retrieve Last Traded Price (LTP), P/E ratio, Net Asset Value (NAV), Dividend Yield, Market Capitalization, 52-week High/Low, and more.
- **📈 Historical Financial Data**:
  - Yearly Dividend History (Cash %, Stock %, Yield %)
  - Annual and Quarterly Earnings Per Share (EPS)
  - Corporate Events (Dividend declarations, AGM schedules, record dates, earnings releases)
- **📑 Format-First Report Generation**: Ask for reports (e.g. *"I want PTL dividend report"*), and finbot interactively prompts for your preferred format before downloading:
  - **PDF Report**: Formatted document generated via ReportLab with header branding and structured tables.
  - **CSV Export**: Clean spreadsheet export generated via Pandas with UTF-8 encoding.
- **🧠 Local LLM Reasoning & Fallback**:
  - Primary: `deepseek-r1:latest` for chain-of-thought analysis and financial reasoning.
  - Fallback: `llama3.2:latest` for rapid responses and high availability.
- **🛡️ Safety & Compliance First**: Strictly informational; gracefully declines buy/sell advice and trading execution.

---

## 🎯 System Workflow

```text
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
---

## 🏗️ Architecture & Project Structure

```text
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

---

## 🚀 Quick Start Guide

### Prerequisites

- **Python**: 3.10+ (tested on Python 3.12)
- **LLM**: API KEY from LLM
- **PostgreSQL**: Accessible instance with `stockdb` schema


```

### Setup Virtual Environment

```bash
# Clone or navigate to the project directory
cd finbot

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Do not commit `.env` or paste credentials into source files.

### Run the Application

```bash
uvicorn app.main:app --port 8000 --reload
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the frontend web interface (`index.html`) |
| `GET` | `/health` | Healthcheck verifying DB and Ollama connection status |
| `POST` | `/chat/` | Sends user query to the AI agent and returns response |
| `GET` | `/export/` | Downloads generated report (`?symbol=PTL&data_type=dividend_history&fmt=pdf`) |

---

## 💬 Example Queries

| Intent | Query Example | Bot Response |
|---|---|---|
| **LTP** | *"What is the LTP of PTL?"* | Returns last traded price and closing data |
| **Dividend History** | *"Show me dividend history for GP"* | Displays historical yearly cash/stock payouts |
| **P/E & NAV** | *"What is BNIPLC PE ratio and NAV?"* | Displays valuation and fundamental multiples |
| **EPS History** | *"Give me RENATA annual EPS"* | Provides multi-year EPS progression |
| **Corporate Events** | *"Latest corporate events for WALTONHIL?"* | Lists recent dividends and AGM announcements |
| **Reports** | *"I want PTL dividend report"* | Prompts user to pick **[PDF]** or **[CSV]** |
| **Trading Advice** | *"Should I buy GP right now?"* | Declines financial advice and provides factual data |

---

## ⚖️ Disclaimer

finbot is strictly for informational and analytical purposes. It does not provide certified financial advice, make trade recommendations, or execute transactions. All market information is derived from internal database records.

