# finbot — In-Memory & Persistent Report Data Store
# Holds query results so export downloads can fetch the exact
# data without re-querying, re-calling LLM, or exposing SQL to the client.

import os
import json
import time
from typing import Any
from app.core.config import REPORTS_DIR

# Cache store: report_id -> {"rows": list[dict], "symbol": str, "data_type": str, "created_at": float}
_CACHE: dict[str, dict[str, Any]] = {}
_LATEST_REPORT_ID: str | None = None
_MAX_AGE_SECONDS = 3600  # 1 hour
_MAX_ITEMS = 100


def _get_latest_filepath() -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return os.path.join(REPORTS_DIR, ".latest_report.json")


def save_report_data(
    report_id: str,
    rows: list[dict],
    symbol: str = "ALL",
    data_type: str = "report",
    sql: str = "",
) -> None:
    """Store report data in memory and persist latest to disk."""
    global _LATEST_REPORT_ID
    now = time.time()

    # Prune expired items
    if len(_CACHE) >= _MAX_ITEMS:
        expired = [
            k for k, v in _CACHE.items()
            if now - v.get("created_at", 0) > _MAX_AGE_SECONDS
        ]
        for k in expired:
            _CACHE.pop(k, None)
        if len(_CACHE) >= _MAX_ITEMS:
            oldest_key = min(_CACHE.keys(), key=lambda k: _CACHE[k].get("created_at", 0))
            _CACHE.pop(oldest_key, None)

    entry = {
        "report_id": report_id,
        "rows": rows,
        "symbol": symbol,
        "data_type": data_type,
        "sql": sql,
        "created_at": now,
    }
    _CACHE[report_id] = entry
    _LATEST_REPORT_ID = report_id

    # Persist to disk so uvicorn reloads do not lose the cached report data
    try:
        with open(_get_latest_filepath(), "w", encoding="utf-8") as f:
            json.dump(entry, f, default=str)
    except Exception as exc:
        print(f"[ReportStore] Warning: could not write disk cache: {exc}")


def get_report_data(report_id: str | None = None) -> dict[str, Any] | None:
    """
    Retrieve cached report data.
    1. If report_id given, check in-memory cache.
    2. Fall back to latest in-memory report.
    3. Fall back to latest report persisted on disk.
    """
    # 1. Direct match in memory
    if report_id and report_id in _CACHE:
        return _CACHE[report_id]

    # 2. Latest in memory
    if _LATEST_REPORT_ID and _LATEST_REPORT_ID in _CACHE:
        return _CACHE[_LATEST_REPORT_ID]

    # 3. Read from disk cache
    try:
        path = _get_latest_filepath()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("rows"):
                    return data
    except Exception as exc:
        print(f"[ReportStore] Warning: could not read disk cache: {exc}")

    return None
