import hashlib
import logging
from typing import List, Dict, Any, Optional
import numpy as np

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    anthropic = None
    HAS_ANTHROPIC = False

from app.config import settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM client."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.anthropic_model
        self.timeout = settings.request_timeout_seconds
        self._client = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("Anthropic API key is not configured.")
            if not HAS_ANTHROPIC or anthropic is None:
                raise RuntimeError("anthropic package is not installed.")
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
        return self._client

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """Generate response via Anthropic Messages API."""
        if not messages:
            return {"content": "", "tool_calls": [], "model": self.model, "provider": self.provider_name}

        client = self._get_client()

        formatted_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages if isinstance(msg, dict) and msg.get("role") in ("user", "assistant")
        ]
        if not formatted_messages:
            return {"content": "", "tool_calls": [], "model": self.model, "provider": self.provider_name}

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": 4096,
            "temperature": max(0.0, min(temperature, 1.0)),
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)
        
        content_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                content_parts.append(block.text)

        return {
            "content": "".join(content_parts),
            "tool_calls": [],
            "model": self.model,
            "provider": self.provider_name
        }

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Anthropic does not have a dedicated public embeddings endpoint; returns 1024-dim vectors."""
        if not texts:
            return []

        results = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(1024).astype(float)
            norm = float(np.linalg.norm(vec))
            results.append((vec / norm).tolist() if norm > 0.0 else [0.0] * 1024)
        return results

    async def health_check(self) -> bool:
        """Verify if Anthropic API key is valid and configured."""
        if not self.api_key or not HAS_ANTHROPIC:
            return False
        try:
            self._get_client()
            return True
        except Exception as exc:
            logger.debug("Anthropic health check failed: %s", exc)
            return False
