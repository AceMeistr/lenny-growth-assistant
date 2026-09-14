import logging
from typing import List, Dict, Any, Optional
import httpx

from app.config import settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """External OpenAI and OpenAI-compatible API provider (Groq, Together, DeepSeek, etc.)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.api_key = api_key or ""
        self.model = model or "gpt-4o-mini"
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = settings.request_timeout_seconds

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """Generate response via standard OpenAI chat completions endpoint."""
        if not messages:
            return {"content": "", "tool_calls": [], "model": self.model, "provider": self.provider_name}

        if not self.api_key:
            raise ValueError("OpenAI API key is required to use external OpenAI provider.")

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                formatted_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": max(0.0, min(temperature, 1.0))
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            content = choices[0].get("message", {}).get("content", "") if choices else ""

            return {
                "content": content,
                "tool_calls": [],
                "model": self.model,
                "provider": self.provider_name
            }

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI text-embedding-3-small or fallback vectors."""
        if not texts:
            return []

        if not self.api_key:
            return [[0.0] * 3072 for _ in texts]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "text-embedding-3-small",
            "input": texts
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/embeddings", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                items = data.get("data", [])
                return [item.get("embedding", []) for item in items]
        except Exception as exc:
            logger.warning("External OpenAI embeddings call failed: %s", exc)
            return [[0.0] * 3072 for _ in texts]

    async def health_check(self) -> bool:
        """Check if API key is provided."""
        return bool(self.api_key)
