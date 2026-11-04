# finbot - Gemini LLM Service

import re
import httpx
import logging

from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_FALLBACK_MODEL,
    GEMINI_MODEL,
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


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


async def ask_llm(prompt: str) -> str:
    model = GEMINI_MODEL

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await _generate(client, model, prompt)

            if response.status_code in (404, 429, 503) and model != GEMINI_FALLBACK_MODEL:
                logger.warning(
                    "Gemini model '%s' returned HTTP %s, falling back to '%s'",
                    model,
                    response.status_code,
                    GEMINI_FALLBACK_MODEL,
                )
                model = GEMINI_FALLBACK_MODEL
                response = await _generate(client, model, prompt)

            response.raise_for_status()
            return _extract_text(response.json())

    except Exception as exc:
        raise RuntimeError(f"Gemini API request failed ({model}): {exc}") from exc