# ──────────────────────────────────────────────
#  finbot — Database Engine (SQLAlchemy)
# ──────────────────────────────────────────────

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import FINANCIAL_DB_URI

engine = create_engine(
    FINANCIAL_DB_URI,
    pool_pre_ping=True,      # reconnect on stale connections
    pool_size=5,
    max_overflow=10,
    echo=False,              # set True for SQL debug logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Returns True if database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
