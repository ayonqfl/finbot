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


def get_stock_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_stockdb_schema(schema: str = "public") -> dict:
    query = """
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns
            WHERE table_schema = :schema
        ORDER BY table_name, ordinal_position
    """

    with engine.connect() as connection:
        result = connection.execute(text(query), {"schema": schema})
        schema_info = result.fetchall()

    schema_dict = {}
    for table, column, dtype in schema_info:
        schema_dict.setdefault(table, []).append(f"{column} ({dtype})")

    return schema_dict


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
