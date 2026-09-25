"""
LLM Provider Abstraction Layer.

Supports:
  - Anthropic Claude (cloud)
  - OpenAI GPT  (cloud)
  - Ollama       (local, any pulled model)

All providers expose an identical async `complete(messages) -> str` interface.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


SYSTEM_PROMPT = """You are the **Lenny Growth Assistant** — an expert AI trained on Lenny Rachitsky's podcast transcripts.

You help product managers, founders, and growth practitioners extract actionable insights from Lenny's interviews.

Rules:
1. Ground every answer in the provided transcript context. If the context doesn't cover the question, say so clearly.
2. Always cite your sources (episode title + guest name).
3. Be concise, practical, and insight-dense.
4. Never fabricate quotes or statistics.
5. If asked to write a Ship 30 for 30 essay, follow the Ship 30 framework precisely."""



class BaseLLMProvider:
    async def complete(self, messages: list[dict], system: str = SYSTEM_PROMPT) -> str:
        raise NotImplementedError

    async def stream_complete(
        self, messages: list[dict], system: str = SYSTEM_PROMPT
    ) -> AsyncIterator[str]:
        """Default: fall back to non-streaming, yield whole response at once."""
        result = await self.complete(messages, system)
        yield result

    async def health_check(self) -> bool:
        raise NotImplementedError



class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
            self.model = model
        except ImportError:
            raise RuntimeError("anthropic package not installed")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def complete(self, messages: list[dict], system: str = SYSTEM_PROMPT) -> str:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    async def stream_complete(
        self, messages: list[dict], system: str = SYSTEM_PROMPT
    ) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        try:
            await self.complete([{"role": "user", "content": "ping"}],
                                system="Reply with: pong")
            return True
        except Exception as e:
            logger.warning(f"Anthropic health check failed: {e}")
            return False



class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)
            self.model = model
        except ImportError:
            raise RuntimeError("openai package not installed")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def complete(self, messages: list[dict], system: str = SYSTEM_PROMPT) -> str:
        all_messages = [{"role": "system", "content": system}] + messages
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            max_tokens=4096,
        )
        return response.choices[0].message.content

    async def stream_complete(
        self, messages: list[dict], system: str = SYSTEM_PROMPT
    ) -> AsyncIterator[str]:
        all_messages = [{"role": "system", "content": system}] + messages
        async with await self._client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            max_tokens=4096,
            stream=True,
        ) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    async def health_check(self) -> bool:
        try:
            await self.complete([{"role": "user", "content": "ping"}],
                                system="Reply with: pong")
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False



class OllamaProvider(BaseLLMProvider):
    def __init__(self, base_url: str, model: str, think: bool = False):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.think = think

    def _build_payload(self, messages: list[dict], stream: bool = False) -> dict:
        processed = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "user" and i == len(messages) - 1:
                processed.append({**msg, "content": "/no_think\n" + msg["content"]})
            else:
                processed.append(msg)
        return {
            "model": self.model,
            "messages": processed,
            "stream": stream,
        }

    async def complete(self, messages: list[dict], system: str = SYSTEM_PROMPT) -> str:
        all_messages = [{"role": "system", "content": system}] + messages
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=self._build_payload(all_messages, stream=False),
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                if not content:
                    logger.error(f"Ollama returned empty content. Full response: {data}")
                    raise RuntimeError("Ollama returned an empty response. The model may have timed out or rejected the prompt.")
                return content
            except httpx.ConnectError:
                raise RuntimeError(
                    "Ollama is not running. Start it with: `ollama serve`"
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise RuntimeError(
                        f"Model '{self.model}' not found in Ollama. "
                        f"Pull it with: `ollama pull {self.model}`"
                    )
                raise

    async def stream_complete(
        self, messages: list[dict], system: str = SYSTEM_PROMPT
    ) -> AsyncIterator[str]:
        all_messages = [{"role": "system", "content": system}] + messages
        async with httpx.AsyncClient(timeout=180.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=self._build_payload(all_messages, stream=True),
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if data.get("message", {}).get("role") == "think":
                                continue
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
            except httpx.ConnectError:
                raise RuntimeError("Ollama is not running. Start it with: `ollama serve`")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    if not any(self.model in m for m in models):
                        logger.warning(
                            f"Ollama is running but model '{self.model}' is not pulled. "
                            f"Run: ollama pull {self.model}"
                        )
                    return True
                return False
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False



_current_provider: Optional[BaseLLMProvider] = None
_current_provider_name: str = ""
_current_model_name: str = ""


def build_provider(
    provider: str | None = None,
    model_name: str | None = None,
    think: bool = False,
    api_key_override: str | None = None,
) -> BaseLLMProvider:
    """Build an LLM provider instance from settings or explicit overrides.

    api_key_override: if provided, uses this key instead of settings/.env.
    Runtime keys from the settings API are checked automatically.
    """
    from app.api.settings import get_runtime_key

    s = settings
    prov = (provider or s.llm_provider).lower()

    if prov == "anthropic":
        model = model_name or s.claude_model
        key = api_key_override or get_runtime_key("anthropic") or s.anthropic_api_key
        if not key:
            raise ValueError(
                "No Anthropic API key found. Add it via Settings → API Key, "
                "or set ANTHROPIC_API_KEY in your .env file."
            )
        return AnthropicProvider(api_key=key, model=model)

    elif prov == "openai":
        model = model_name or s.openai_model
        key = api_key_override or get_runtime_key("openai") or s.openai_api_key
        if not key:
            raise ValueError(
                "No OpenAI API key found. Add it via Settings → API Key, "
                "or set OPENAI_API_KEY in your .env file."
            )
        return OpenAIProvider(api_key=key, model=model)

    elif prov == "ollama":
        model = model_name or s.ollama_model
        return OllamaProvider(base_url=s.ollama_base_url, model=model, think=think)

    else:
        raise ValueError(f"Unknown LLM provider: {prov!r}. Choose anthropic | openai | ollama")


def get_provider(
    provider: str | None = None,
    model_name: str | None = None,
) -> tuple[BaseLLMProvider, str, str]:
    """
    Returns (provider_instance, provider_name, model_name).
    Automatically uses runtime-configured keys from the settings API.
    """
    global _current_provider, _current_provider_name, _current_model_name

    s = settings
    prov = (provider or s.llm_provider).lower()

    if prov == "anthropic":
        mname = model_name or s.claude_model
    elif prov == "openai":
        mname = model_name or s.openai_model
    elif prov == "ollama":
        mname = model_name or s.ollama_model
    else:
        raise ValueError(f"Unknown provider: {prov}")

    if (
        _current_provider is not None
        and _current_provider_name == prov
        and _current_model_name == mname
    ):
        return _current_provider, prov, mname

    _current_provider = build_provider(prov, mname)
    _current_provider_name = prov
    _current_model_name = mname
    return _current_provider, prov, mname
