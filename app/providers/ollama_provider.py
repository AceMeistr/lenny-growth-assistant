import logging
from typing import List, Dict, Any, Optional
import httpx

from app.config import settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama local model client using the native Ollama REST API."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.embed_model = settings.ollama_embed_model
        self.timeout = settings.request_timeout_seconds

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """Generate response via Ollama /api/chat endpoint."""
        if not messages:
            return {"content": "", "tool_calls": [], "model": self.model, "provider": self.provider_name}

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                formatted_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False,
            "options": {
                "temperature": max(0.0, min(temperature, 1.0))
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")

            return {
                "content": content,
                "tool_calls": [],
                "model": self.model,
                "provider": self.provider_name
            }

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Ollama /api/embeddings endpoint."""
        if not texts:
            return []

        embeddings: List[List[float]] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for text in texts:
                payload = {
                    "model": self.embed_model,
                    "prompt": text
                }
                try:
                    response = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                    response.raise_for_status()
                    emb = response.json().get("embedding", [])
                    if emb:
                        embeddings.append(emb)
                    else:
                        logger.warning("Empty embedding vector returned by Ollama for model %s", self.embed_model)
                        embeddings.append([0.0] * 3072)
                except Exception as exc:
                    logger.warning("Ollama embeddings failed for model '%s': %s", self.embed_model, exc)
                    embeddings.append([0.0] * 3072)
        return embeddings

    async def health_check(self) -> bool:
        """Check if local Ollama server is running and responding."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
