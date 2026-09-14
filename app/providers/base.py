"""
Abstract base class and contract for all LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class LLMProvider(ABC):
    """Abstract strategy for cloud and local LLM execution."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique provider name (e.g. 'anthropic', 'ollama')."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Generate a conversational response or tool call.
        Returns a dictionary containing:
        - 'content': str
        - 'tool_calls': List[Dict[str, Any]] (if any)
        - 'model': str
        - 'provider': str
        """
        pass

    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for a list of text strings."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify reachability and authentication of the provider."""
        pass
