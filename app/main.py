#  finbot — FastAPI Application Entry Point

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import APP_TITLE, APP_VERSION
from app.core.database import check_db_connection, get_stockdb_schema
from app.services.llm import check_llm
from app.api.chat import router as chat_router
from app.api.export import router as export_router

# App Init
app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="Bangladesh OMS Financial Analysis Chatbot — powered by Ollama + PostgreSQL",
)

# CORS (open — R&D project, no auth)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Routers
app.include_router(chat_router,   prefix="/chat",   tags=["Chat"])
app.include_router(export_router, prefix="/export",  tags=["Export"])

# Static Files (frontend)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/health", tags=["System"])
async def health():
    db_ok  = check_db_connection()
    llm_ok = await check_llm()
    status = "ok" if (db_ok and llm_ok) else "degraded"

    return JSONResponse(content={
        "db":       "ok" if db_ok else "error",
        "llm":      "ok" if llm_ok else "error",
        "status": status
    })

@app.get("/schema", tags=["System"])
async def schema():
    return JSONResponse(content={"status": 'Success', "schema": get_stockdb_schema()})


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("frontend/index.html")
