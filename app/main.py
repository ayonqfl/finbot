# ──────────────────────────────────────────────
#  finbot — FastAPI Application Entry Point
# ──────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import APP_TITLE, APP_VERSION
from app.core.database import check_db_connection
from app.services.llm import check_ollama
from app.api.chat import router as chat_router
from app.api.export import router as export_router

# ── App Init ───────────────────────────────────

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="Bangladesh OMS Financial Analysis Chatbot — powered by Ollama + PostgreSQL",
)

# ── CORS (open — R&D project, no auth) ─────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────

app.include_router(chat_router,   prefix="/chat",   tags=["Chat"])
app.include_router(export_router, prefix="/export",  tags=["Export"])

# ── Static Files (frontend) ────────────────────

app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ── Health Check ───────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    """Check DB and Ollama connectivity."""
    db_ok     = check_db_connection()
    ollama_ok = await check_ollama()
    status    = "ok" if (db_ok and ollama_ok) else "degraded"
    return JSONResponse(content={
        "status": status,
        "db":     "ok" if db_ok else "error",
        "ollama": "ok" if ollama_ok else "error",
    })


# ── Root → Serve Chat UI ───────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Serve the chat UI at root URL."""
    return FileResponse("frontend/index.html")
