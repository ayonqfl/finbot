#  finbot — Chat API Endpoint
import json
import asyncio
import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from app.models.financial import ChatRequest
from app.services.agent import run_agent, run_agent_stream

router = APIRouter()


@router.post("/")
async def chat(request: ChatRequest):
    try:
        result = await run_agent(request.message)
        return JSONResponse(content=jsonable_encoder(result))

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"type": "error", "content": f"Agent error: {str(e)}"})

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        try:
            async for event in run_agent_stream(request.message):
                yield f"event: {event['type']}\n"
                yield f"data: {json.dumps(jsonable_encoder(event), ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            traceback.print_exc()
            yield "event: error\n"
            yield f"data: {json.dumps({'type': 'error', 'content': f'Agent error: {exc}'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
