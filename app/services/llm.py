# finbot - Gemini LLM Service

import re
import httpx
import logging
import json
from collections.abc import AsyncIterator

from app.core.config import (
    GEMINI_API_KEY,
    PRIMARY_MODEL,
    FALLBACK_MODEL,
    BASE_URL,
)

logger = logging.getLogger(__name__)

HEADERS = {"x-goog-api-key": GEMINI_API_KEY or ""}

async def check_llm() -> bool:
    if not GEMINI_API_KEY:
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BASE_URL}/models", headers=HEADERS)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


async def _generate(client: httpx.AsyncClient, model: str, prompt: str) -> httpx.Response:
    return await client.post(
        f"{BASE_URL}/models/{model}:generateContent",
        headers=HEADERS,
        json={"contents": [{"parts": [{"text": prompt}]}]},
    )


def _extract_text(data: dict, *, strip_whitespace: bool = True) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip() if strip_whitespace else text


async def ask_llm(prompt: str) -> str:
    model = PRIMARY_MODEL

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await _generate(client, model, prompt)

            if response.status_code in (404, 429, 503) and model != FALLBACK_MODEL:
                logger.warning(
                    "Gemini model '%s' returned HTTP %s, falling back to '%s'",
                    model,
                    response.status_code,
                    FALLBACK_MODEL,
                )
                model = FALLBACK_MODEL
                response = await _generate(client, model, prompt)

            response.raise_for_status()
            return _extract_text(response.json())

    except Exception as exc:
        raise RuntimeError(f"Gemini API request failed ({model}): {exc}") from exc


async def ask_llm_stream(prompt: str) -> AsyncIterator[str]:
    """Stream Gemini text chunks. Falls back once on model/API availability errors."""
    model = PRIMARY_MODEL

    async def stream_model(client: httpx.AsyncClient, selected_model: str) -> AsyncIterator[str]:
        url = f"{BASE_URL}/models/{selected_model}:streamGenerateContent"
        async with client.stream(
            "POST",
            url,
            headers=HEADERS,
            params={"alt": "sse"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        ) as response:
            if response.status_code in (404, 429, 503) and selected_model != FALLBACK_MODEL:
                return
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                text = _extract_text(data, strip_whitespace=False)
                if text:
                    yield text

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
            emitted = False
            async for chunk in stream_model(client, model):
                emitted = True
                yield chunk

            if not emitted and model != FALLBACK_MODEL:
                logger.warning("Gemini streaming model '%s' produced no chunks, falling back to '%s'", model, FALLBACK_MODEL)
                async for chunk in stream_model(client, FALLBACK_MODEL):
                    yield chunk
    except Exception as exc:
        raise RuntimeError(f"Gemini streaming request failed ({model}): {exc}") from exc