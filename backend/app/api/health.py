"""
Health check endpoint.
"""
from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.services import rag as rag_service
from app.services.llm import get_provider
from app.config import get_settings

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Returns system health status including DB, LLM, and RAG index."""
    try:
        provider, pname, mname = get_provider()
        llm_ok = await provider.health_check()
        llm_status = f"{pname}/{mname}" if llm_ok else f"{pname}/{mname} (unreachable)"
    except Exception as e:
        pname, mname = settings.llm_provider, "unknown"
        llm_status = f"error: {e}"

    return HealthResponse(
        status="ok",
        db="connected",
        llm_provider=pname,
        llm_model=mname,
        rag_index_size=rag_service.index_size(),
    )


@router.get("/")
async def root():
    return {
        "name": "Lenny Growth Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
