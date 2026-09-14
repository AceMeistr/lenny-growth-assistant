import pytest
from app.config import settings
from app.providers.factory import ProviderFactory
from app.providers.ollama_provider import OllamaProvider


@pytest.mark.asyncio
async def test_ollama_provider_resolution():
    provider = ProviderFactory.get_provider("ollama")
    assert isinstance(provider, OllamaProvider)
    assert provider.provider_name == "ollama"
    assert provider.model == "phi3"
    assert provider.embed_model == "phi3"


@pytest.mark.asyncio
async def test_ollama_phi3_embeddings():
    provider = OllamaProvider()
    texts = ["Product-led growth framework", "Retention and churn metrics"]
    embeddings = await provider.get_embeddings(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 3072
    assert len(embeddings[1]) == 3072


@pytest.mark.asyncio
async def test_ollama_empty_inputs_safety():
    provider = OllamaProvider()
    assert await provider.get_embeddings([]) == []
    empty_resp = await provider.generate_response([])
    assert empty_resp["content"] == ""
