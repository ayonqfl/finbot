import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).with_name('.env'))

# PostgreSQL
FINANCIAL_DB_URI = os.getenv("FINANCIAL_DB_URI", None)

# Google Gemini Settings
BASE_URL = os.getenv("GEMINI_BASE_URL","https://generativelanguage.googleapis.com/v1beta")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", None)
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", None)
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", None)

# Report output directory
REPORTS_DIR = "reports"

# App metadata
APP_TITLE = "finbot — OMS Financial Chatbot"
APP_VERSION = "1.0.0"
