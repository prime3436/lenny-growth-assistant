"""
Tests for the LLM provider abstraction layer.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm import OllamaProvider, AnthropicProvider, get_provider, build_provider


class TestOllamaProvider:
    """Test Ollama local provider — no real network calls."""

    @pytest.fixture
    def provider(self):
        return OllamaProvider(base_url="http://localhost:11434", model="llama3.2")

    @pytest.mark.asyncio
    async def test_complete_success(self, provider):
        mock_response = {"message": {"content": "This is a test response"}}
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await provider.complete([{"role": "user", "content": "test"}])
            assert result == "This is a test response"

    @pytest.mark.asyncio
    async def test_connect_error_raises_helpful_message(self, provider):
        import httpx
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Ollama is not running"):
                await provider.complete([{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        mock_tags = {"models": [{"name": "llama3.2:latest"}]}
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_tags
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            ok = await provider.health_check()
            assert ok is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        import httpx
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            ok = await provider.health_check()
            assert ok is False


class TestProviderFactory:
    def test_build_ollama_provider(self):
        from app.services.llm import build_provider
        p = build_provider("ollama", "llama3.2")
        assert isinstance(p, OllamaProvider)
        assert p.model == "llama3.2"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            build_provider("grok", "grok-1")

    def test_anthropic_without_key_raises(self):
        with patch("app.services.llm.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            mock_settings.llm_provider = "anthropic"
            mock_settings.claude_model = "claude-3-5-sonnet-20241022"
            with pytest.raises((ValueError, RuntimeError)):
                build_provider("anthropic", "claude-3-5-sonnet-20241022")
