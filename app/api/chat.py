# ──────────────────────────────────────────────
#  finbot — Chat API Endpoint
#  POST /chat  → JSON response
# ──────────────────────────────────────────────

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from app.models.financial import ChatRequest
from app.services.agent import run_agent

router = APIRouter()


@router.post("/")
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Accepts user message, returns agent response as JSON.

    Response types:
      { type: "text",       content: "..." }
      { type: "ask_format", content: "...", symbol: "PTL", data_type: "dividend_history" }
      { type: "error",      content: "..." }
    """
    try:
        result = await run_agent(request.message)
        return JSONResponse(content=jsonable_encoder(result))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"type": "error", "content": f"Agent error: {str(e)}"}
        )
