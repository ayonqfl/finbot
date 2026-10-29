# 🤖 finbot — Bangladesh DSE Financial Assistant

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

## 🏗️ Architecture & Project Structure

```text
finbot/
├── app/
│   ├── api/
│   │   ├── chat.py           # POST /chat/ — chat request handler
│   │   └── export.py         # GET /export/ — PDF/CSV file download endpoint
│   ├── core/
│   │   ├── config.py         # App configuration, DB URI, Ollama parameters
│   │   └── database.py       # SQLAlchemy engine, session maker, connection check
│   ├── models/
│   │   └── financial.py      # Pydantic schemas (ChatRequest, BasicInfo, etc.)
│   ├── services/
│   │   ├── agent.py          # Intent detection, DB-validated ticker extractor & routing
│   │   ├── db_tools.py       # Parameterized SQL query functions for 6 DSE tables
│   │   ├── llm.py            # Ollama API wrapper with automatic model fallback
│   │   └── report.py         # ReportLab (PDF) & Pandas (CSV) generators
│   └── main.py               # FastAPI app assembly, CORS, static file mount
│
├── frontend/
│   ├── css/
│   │   └── styles.css        # Glassmorphism dark theme UI
│   ├── js/
│   │   └── chat.js           # Chat UI interaction, format picker & download handler
│   └── index.html            # Main web interface
│
├── reports/                  # Generated PDF & CSV files directory
├── sql/
│   └── schema_reference.sql  # DDL reference for stock database tables
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🗄️ Database Tables Used

All data is queried read-only from PostgreSQL (`stockdb`):

| Table Name | Description | Key Data |
|---|---|---|
| `basic_info` | Core stock fundamentals | LTP (`yesterday_close`), P/E, NAV, Market Cap, 52W High/Low |
| `dividend_history` | Historical dividend records | Year, Cash %, Stock %, Yield % |
| `financial_annual` | Annual EPS records | Fiscal year, Annual EPS |
| `financial_quarterly` | Quarterly earnings records | Quarter (Q1-Q4), Period date, EPS |
| `corporate_event` | Corporate action events | Declaration date, news type, actual value, impact |
| `dividend_corp_action` | Declared corporate actions | Dividend rate, record date, AGM date |

---

## 🚀 Quick Start Guide

### 1. Prerequisites

- **Python**: 3.10+ (tested on Python 3.12)
- **Ollama**: Installed and running locally
- **PostgreSQL**: Accessible instance with `stockdb` schema

### 2. Pull Ollama Models

Make sure Ollama is running and download the models:
```bash
ollama serve
ollama pull deepseek-r1:latest
ollama pull llama3.2:latest
```

### 3. Setup Virtual Environment

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

### 4. Configure Environment

Review or adjust database and model settings in `app/core/config.py`:
```python
FINANCIAL_DB_URI = "postgresql+psycopg2://user:password@host:port/stockdb"
OLLAMA_BASE_URL  = "http://localhost:11434"
PRIMARY_MODEL    = "deepseek-r1:latest"
FALLBACK_MODEL   = "llama3.2:latest"
REPORTS_DIR      = "reports"
```

### 5. Run the Application

```bash
uvicorn app.main:app --port 8000 --reload
```

Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

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

