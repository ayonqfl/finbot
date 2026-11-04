import os

from dotenv import load_dotenv

load_dotenv()

# PostgreSQL
FINANCIAL_DB_URI = os.getenv("FINANCIAL_DB_URI", "")

# Google Gemini Settings
BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta",
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_FALLBACK_MODEL = os.getenv(
    "GEMINI_FALLBACK_MODEL",
    "gemini-3.5-flash-lite",
)

# Primary model alias for backwards compatibility
PRIMARY_MODEL = GEMINI_MODEL
FALLBACK_MODEL = GEMINI_FALLBACK_MODEL

# Report output directory
REPORTS_DIR = "reports"

# App
APP_TITLE = "finbot — OMS Financial Chatbot"
APP_VERSION = "1.0.0"
