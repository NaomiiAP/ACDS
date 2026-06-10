"""
groq_client.py — Async HTTP client for the Groq Cloud LLM API.
"""

import asyncio
import logging
import os
import httpx

log = logging.getLogger("llm_triage.groq")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"


class GroqClient:
    """Async wrapper around the Groq OpenAI-compatible API."""

    def __init__(self, api_key: str = None, model: str = DEFAULT_MODEL):
        # Dynamically fetch key if not provided, allowing .env to load first
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self._client = httpx.AsyncClient(timeout=30.0)
        
        if not self.api_key:
            log.warning("GROQ_API_KEY not found in environment!")
        else:
            log.info("GroqClient initialized (Model: %s)", self.model)

    async def close(self):
        await self._client.aclose()

    async def generate(self, prompt: str) -> str:
        """Send a prompt to Groq and return the generated text."""
        if not self.api_key:
            return "Error: GROQ_API_KEY missing"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a cyber security expert analyzing network alerts."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        for attempt in range(3):
            try:
                response = await self._client.post(
                    GROQ_API_URL, headers=headers, json=payload,
                )
                if response.status_code == 429:
                    retry_after = float(response.headers.get("retry-after", 2 ** attempt))
                    log.warning("Groq rate limit (429), retrying in %.1fs", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                log.error("Groq API request failed: %s", exc)
                return f"Error: {exc}"
            except Exception as exc:
                log.error("Groq API request failed: %s", exc)
                return f"Error: {str(exc)}"

        return "Error: Groq rate limit exceeded — try again in a moment"

    async def is_available(self) -> bool:
        """Check whether the Groq API key is present."""
        return len(self.api_key) > 0
