# ──────────────────────────────────────────────
#  finbot — Core Configuration
# ──────────────────────────────────────────────

# PostgreSQL
FINANCIAL_DB_URI = "postgresql+psycopg2://stockdata:pass4321@192.168.155.22:5446/stockdb"

# Ollama
OLLAMA_BASE_URL = "http://localhost:11434"
PRIMARY_MODEL   = "deepseek-r1:latest"
FALLBACK_MODEL  = "llama3.2:latest"

# Report output directory (relative to project root)
REPORTS_DIR = "reports"

# App
APP_TITLE   = "finbot — OMS Financial Chatbot"
APP_VERSION = "1.0.0"
