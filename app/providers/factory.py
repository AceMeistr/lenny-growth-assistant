"""
Provider factory with resilient fallback mechanics per architecture.md ADR-1.
"""

import logging
from typing import Tuple, Optional, Any
from app.config import settings
from app.providers.base import LLMProvider
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Resolves active LLMProvider and orchestrates seamless fallback."""

    @staticmethod
    def get_provider(
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> LLMProvider:
        """Resolve requested provider or default from configuration."""
        name = (provider_name or settings.llm_provider).lower()
        if name == "anthropic":
            return AnthropicProvider(api_key=api_key, model=model)
        elif name in ("openai", "custom"):
            return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
        elif name == "ollama":
            return OllamaProvider(base_url=base_url, model=model)
        else:
            logger.warning("Unknown provider '%s', defaulting to ollama", name)
            return OllamaProvider(base_url=base_url, model=model)

    @staticmethod
    async def execute_with_fallback(
        provider: LLMProvider,
        func_name: str,
        *args,
        **kwargs
    ) -> Tuple[Any, bool]:
        """
        Executes a method on the provider. If it fails and fallback is enabled,
        retries with the local Ollama provider.
        Returns: (result, fallback_used: bool)
        """
        try:
            method = getattr(provider, func_name)
            res = await method(*args, **kwargs)
            return res, False
        except Exception as primary_exc:
            logger.error("Primary provider '%s' failed: %s", provider.provider_name, str(primary_exc))
            
            # If primary was already Ollama or fallback is disabled, re-raise
            if provider.provider_name == "ollama" or not settings.llm_fallback_to_local:
                raise primary_exc

            logger.info("Executing graceful fallback to local Ollama provider...")
            try:
                fallback_provider = OllamaProvider()
                method = getattr(fallback_provider, func_name)
                res = await method(*args, **kwargs)
                return res, True
            except Exception as fallback_exc:
                logger.error("Fallback provider 'ollama' also failed: %s", str(fallback_exc))
                raise RuntimeError(f"Both primary ({primary_exc}) and fallback ({fallback_exc}) providers failed.")
