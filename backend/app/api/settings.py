"""
Settings API — Runtime LLM provider and API key configuration.

Security design:
- Keys stored in server memory ONLY (not DB, not logs, not responses)
- Keys never returned to the client (write-only from client perspective)
- All LLM requests proxied through FastAPI (browser never calls Anthropic/OpenAI directly)
- Ollama is always the default fallback (no key required)
"""
from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm import build_provider, OllamaProvider
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

_runtime_keys: dict[str, str] = {}



class KeyConfigRequest(BaseModel):
    provider: str
    api_key: str


class KeyConfigResponse(BaseModel):
    provider: str
    configured: bool
    message: str


class ProviderStatusResponse(BaseModel):
    ollama: dict
    anthropic: dict
    openai: dict


class TestConnectionResponse(BaseModel):
    provider: str
    success: bool
    message: str



def get_runtime_key(provider: str) -> Optional[str]:
    """Get a runtime-configured API key. Returns None if not set."""
    return _runtime_keys.get(provider)


def has_any_key(provider: str) -> bool:
    """Check if a key is available (runtime or .env)."""
    settings = get_settings()
    if provider == "anthropic":
        return bool(_runtime_keys.get("anthropic") or settings.anthropic_api_key)
    elif provider == "openai":
        return bool(_runtime_keys.get("openai") or settings.openai_api_key)
    elif provider == "ollama":
        return True
    return False



@router.post("/keys", response_model=KeyConfigResponse)
async def configure_api_key(body: KeyConfigRequest):
    """
    Store an API key in server memory for runtime use.
    The key is NEVER returned to the client, logged, or persisted.
    """
    provider = body.provider.lower().strip()
    if provider not in ("anthropic", "openai"):
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' does not need an API key. Only 'anthropic' and 'openai' are supported."
        )

    if not body.api_key or len(body.api_key.strip()) < 10:
        raise HTTPException(status_code=400, detail="API key appears invalid (too short).")

    key = body.api_key.strip()
    if provider == "anthropic" and not key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=400,
            detail="Anthropic API keys must start with 'sk-ant-'. Please check your key."
        )
    if provider == "openai" and not key.startswith("sk-"):
        raise HTTPException(
            status_code=400,
            detail="OpenAI API keys must start with 'sk-'. Please check your key."
        )

    _runtime_keys[provider] = key
    logger.info(f"API key configured for provider: {provider} (key not logged)")

    return KeyConfigResponse(
        provider=provider,
        configured=True,
        message=f"{provider.capitalize()} API key saved. Switch to this provider to use it."
    )


@router.get("/providers", response_model=ProviderStatusResponse)
async def get_provider_status():
    """
    Returns which providers are configured (key available).
    Never returns key values — only boolean configured status.
    """
    settings = get_settings()

    anthropic_configured = bool(_runtime_keys.get("anthropic") or settings.anthropic_api_key)
    openai_configured = bool(_runtime_keys.get("openai") or settings.openai_api_key)

    return ProviderStatusResponse(
        ollama={
            "configured": True,
            "label": "Ollama (Local)",
            "note": "No API key required — runs on your machine",
        },
        anthropic={
            "configured": anthropic_configured,
            "label": "Anthropic Claude",
            "note": "Configured via settings" if anthropic_configured else "API key required",
        },
        openai={
            "configured": openai_configured,
            "label": "OpenAI GPT-4o",
            "note": "Configured via settings" if openai_configured else "API key required",
        },
    )


@router.post("/test", response_model=TestConnectionResponse)
async def test_connection(body: dict):
    """Test if the configured provider is working."""
    provider = body.get("provider", "ollama").lower()
    settings = get_settings()

    try:
        if provider == "ollama":
            p = build_provider("ollama")
            ok = await p.health_check()
            return TestConnectionResponse(
                provider=provider,
                success=ok,
                message="Ollama is running and reachable." if ok else "Ollama is not reachable. Is it running?"
            )

        elif provider == "anthropic":
            key = _runtime_keys.get("anthropic") or settings.anthropic_api_key
            if not key:
                return TestConnectionResponse(
                    provider=provider, success=False,
                    message="No Anthropic API key configured. Add it in Settings first."
                )
            p = build_provider("anthropic")
            result = await p.complete(
                [{"role": "user", "content": "Reply with exactly: OK"}],
                system="You are a test assistant."
            )
            return TestConnectionResponse(
                provider=provider, success=bool(result),
                message="Anthropic Claude is connected and responding." if result else "Got empty response from Claude."
            )

        elif provider == "openai":
            key = _runtime_keys.get("openai") or settings.openai_api_key
            if not key:
                return TestConnectionResponse(
                    provider=provider, success=False,
                    message="No OpenAI API key configured. Add it in Settings first."
                )
            p = build_provider("openai")
            result = await p.complete(
                [{"role": "user", "content": "Reply with exactly: OK"}],
                system="You are a test assistant."
            )
            return TestConnectionResponse(
                provider=provider, success=bool(result),
                message="OpenAI GPT-4o is connected and responding." if result else "Got empty response from OpenAI."
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    except Exception as e:
        logger.warning(f"Connection test failed for {provider}: {type(e).__name__}")
        return TestConnectionResponse(
            provider=provider, success=False,
            message=f"Connection failed: {str(e)}"
        )
