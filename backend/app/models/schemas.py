"""
Pydantic schemas for request / response validation.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# ── Session ──────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    model: Optional[str] = None  # override default model for this session


class SessionResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    model_provider: str
    model_name: str

    model_config = {"from_attributes": True, "protected_namespaces": ()}


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    message: str
    model_provider: Optional[Literal["anthropic", "openai", "ollama"]] = None
    model_name: Optional[str] = None
    stream: bool = False

    model_config = {"protected_namespaces": ()}


class SourceChunk(BaseModel):
    episode_title: str
    episode_number: Optional[str] = None
    guest: Optional[str] = None
    chunk_text: str
    score: float


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    sources: list[SourceChunk] = []
    model_provider: str
    model_name: str
    created_at: datetime

    model_config = {"protected_namespaces": ()}


# ── Artifact ──────────────────────────────────────────────────────────────────

class ArtifactType(str):
    MARKDOWN = "markdown"
    HTML = "html"
    SHIP30 = "ship30"


class ArtifactGenerateRequest(BaseModel):
    session_id: uuid.UUID
    topic: str
    artifact_type: Literal["markdown", "html", "ship30"] = "ship30"
    model_provider: Optional[Literal["anthropic", "openai", "ollama"]] = None
    model_name: Optional[str] = None

    model_config = {"protected_namespaces": ()}


class ArtifactResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    artifact_type: str
    title: str
    content: str  # raw Markdown / HTML
    sanitized_html: Optional[str] = None  # bleach-sanitized for iframe
    word_count: int
    sources: list[SourceChunk] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Model switching ───────────────────────────────────────────────────────────

class ModelSwitchRequest(BaseModel):
    provider: Literal["anthropic", "openai", "ollama"]
    model_name: Optional[str] = None

    model_config = {"protected_namespaces": ()}


class ModelSwitchResponse(BaseModel):
    provider: str
    model_name: str
    status: str
    message: str

    model_config = {"protected_namespaces": ()}


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    db: str
    llm_provider: str
    llm_model: str
    rag_index_size: int
    version: str = "1.0.0"
