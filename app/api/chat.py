#  finbot — Chat API Endpoint

import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from app.models.financial import ChatRequest
from app.services.agent import run_agent

router = APIRouter()


@router.post("/")
async def chat(request: ChatRequest):
    try:
        result = await run_agent(request.message)
        return JSONResponse(content=jsonable_encoder(result))

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"type": "error", "content": f"Agent error: {str(e)}"})
