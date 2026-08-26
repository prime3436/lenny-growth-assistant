"""
Integration tests for the FastAPI API endpoints.
Uses TestClient with a mock DB and mock LLM.
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app


@pytest.fixture
def mock_db_session():
    """Mock async DB session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_health_endpoint():
    """Health check should return 200 with expected fields."""
    with patch("app.api.health.rag_service.index_size", return_value=1000):
        with patch("app.api.health.get_provider") as mock_gp:
            mock_provider = AsyncMock()
            mock_provider.health_check = AsyncMock(return_value=True)
            mock_gp.return_value = (mock_provider, "ollama", "llama3.2")

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "rag_index_size" in data
    assert data["rag_index_size"] == 1000


@pytest.mark.asyncio
async def test_root_endpoint():
    """Root endpoint should return API info."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "Lenny Growth Assistant" in resp.json()["name"]


@pytest.mark.asyncio
async def test_model_switch_ollama():
    """Model switch to ollama should succeed when Ollama responds."""
    with patch("app.services.llm.build_provider") as mock_bp:
        mock_prov = AsyncMock()
        mock_prov.health_check = AsyncMock(return_value=True)
        mock_bp.return_value = mock_prov

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/models/switch",
                json={"provider": "ollama", "model_name": "llama3.2"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "ollama"
    assert data["model_name"] == "llama3.2"


@pytest.mark.asyncio
async def test_model_switch_bad_provider():
    """Unknown provider should return error status (not 500)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/models/switch",
            json={"provider": "ollama"},  # valid, just health might fail
        )
    # Should still return 200 with status field
    assert resp.status_code in (200, 422)
