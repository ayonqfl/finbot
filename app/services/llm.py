# ──────────────────────────────────────────────
#  finbot — LLM Wrapper (Ollama via LangChain)
# ──────────────────────────────────────────────

import re
import httpx
from app.core.config import OLLAMA_BASE_URL, PRIMARY_MODEL, FALLBACK_MODEL


def strip_think_tags(text: str) -> str:
    """Remove deepseek-r1 <think>...</think> reasoning blocks from output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


async def check_ollama() -> bool:
    """Returns True if Ollama server is reachable."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


async def stream_ollama(prompt: str, model: str = PRIMARY_MODEL):
    """
    Stream tokens from Ollama API.
    Yields clean text tokens (think-tags stripped).
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
    }
    buffer = ""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
        ) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                import json as _json
                try:
                    chunk = _json.loads(line)
                    token = chunk.get("response", "")
                    buffer += token
                    # yield token-by-token but strip think tags from buffer
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
                except Exception:
                    continue


async def ask_ollama(prompt: str, model: str = PRIMARY_MODEL) -> str:
    """
    Non-streaming call to Ollama. Returns full cleaned response.
    Automatically falls back to FALLBACK_MODEL if primary fails or times out.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            r.raise_for_status()
            data = r.json()
            return strip_think_tags(data.get("response", ""))
    except Exception as e:
        if model != FALLBACK_MODEL and FALLBACK_MODEL:
            print(f"[LLM] Primary model '{model}' failed ({e}). Falling back to '{FALLBACK_MODEL}'...")
            payload["model"] = FALLBACK_MODEL
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
                r.raise_for_status()
                data = r.json()
                return strip_think_tags(data.get("response", ""))
        raise
