"""
ollama_client.py — Async HTTP client for the Ollama local LLM API.
"""

import asyncio
import logging
import os

import httpx

log = logging.getLogger("llm_triage.ollama")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b")
TIMEOUT_SECONDS = 60
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


class OllamaClient:
    """Async wrapper around the Ollama REST API."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)

    async def close(self):
        await self._client.aclose()

    async def generate(self, prompt: str) -> str:
        """Send a prompt to Ollama and return the generated text.

        Retries up to MAX_RETRIES times with exponential backoff on failure.
        """
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
            except (httpx.HTTPError, httpx.TimeoutException, Exception) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE ** attempt
                    log.warning(
                        "Ollama request failed (attempt %d/%d): %s — retrying in %ds",
                        attempt, MAX_RETRIES, exc, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    log.error(
                        "Ollama request failed after %d attempts: %s",
                        MAX_RETRIES, exc,
                    )
        raise RuntimeError(f"Ollama generation failed after {MAX_RETRIES} attempts") from last_exc

    async def is_available(self) -> bool:
        """Check whether the Ollama server is reachable."""
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list:
        """Return a list of models available on the Ollama server."""
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
        except Exception as exc:
            log.error("Failed to list Ollama models: %s", exc)
            return []
