"""
Artifacts API — Ship 30 essay generation + Markdown/HTML artifact creation.
"""
from __future__ import annotations

import uuid
import logging
import re
from datetime import datetime, timezone

import bleach
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.database import Session as DBSession, Artifact as DBArtifact
from app.models.schemas import (
    ArtifactGenerateRequest, ArtifactResponse, SourceChunk,
)
from app.services.ship30 import generate_ship30_essay, extract_title, count_words
from app.services.rag import retrieve, format_context
from app.services.llm import get_provider, SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


# ── HTML sanitization ──────────────────────────────────────────────────────────

ALLOWED_TAGS = [
    "p", "br", "strong", "em", "b", "i", "u", "h1", "h2", "h3", "h4",
    "ul", "ol", "li", "blockquote", "code", "pre", "a", "span", "div",
    "table", "thead", "tbody", "tr", "th", "td",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "target"],
    "span": ["class"],
    "div": ["class"],
    "code": ["class"],
}


def sanitize_html(html: str) -> str:
    """Sanitize HTML for safe iframe rendering."""
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


def markdown_to_simple_html(md: str) -> str:
    """
    Very lightweight Markdown → HTML conversion for preview.
    (In production, use a proper library like markdown-it-py.)
    """
    html = md
    # Headers
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    # Italic
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    # Line breaks → paragraphs
    paragraphs = re.split(r"\n\n+", html)
    html = "".join(
        f"<p>{p.strip()}</p>" if not p.strip().startswith("<h") else p.strip()
        for p in paragraphs if p.strip()
    )
    return html


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=ArtifactResponse, status_code=201)
async def generate_artifact(
    body: ArtifactGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an artifact:
      - ship30: ~1,250-word atomic essay following Ship 30 for 30 principles
      - markdown: RAG-grounded markdown document
      - html: Sanitized HTML snippet
    """
    # Validate session
    result = await db.execute(select(DBSession).where(DBSession.id == body.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sources: list[SourceChunk] = []
    content = ""
    title = ""

    try:
        if body.artifact_type == "ship30":
            content, sources = await generate_ship30_essay(
                topic=body.topic,
                provider_name=body.model_provider,
                model_name=body.model_name,
            )
            title = extract_title(content, fallback=body.topic)

        elif body.artifact_type in ("markdown", "html"):
            # Generic RAG-grounded generation
            sources = retrieve(body.topic, top_k=5)
            context = format_context(sources)
            prompt_map = {
                "markdown": (
                    f"Write a detailed, well-structured Markdown document about: **{body.topic}**\n\n"
                    f"Ground your content in the following Lenny's Podcast transcripts:\n\n{context}"
                ),
                "html": (
                    f"Write a clean, semantic HTML snippet (no <html>/<body> wrapper) about: **{body.topic}**\n\n"
                    f"Use only safe HTML tags. Ground content in:\n\n{context}"
                ),
            }
            provider, pname, mname = get_provider(body.model_provider, body.model_name)
            content = await provider.complete(
                messages=[{"role": "user", "content": prompt_map[body.artifact_type]}],
                system=SYSTEM_PROMPT,
            )
            title = body.topic[:80]

        else:
            raise HTTPException(status_code=400, detail=f"Unknown artifact type: {body.artifact_type}")

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Artifact generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Artifact generation failed")

    # Sanitize to HTML for iframe viewer
    if body.artifact_type == "html":
        sanitized = sanitize_html(content)
    else:
        sanitized = sanitize_html(markdown_to_simple_html(content))

    word_count = count_words(content)

    # Persist artifact
    artifact = DBArtifact(
        session_id=body.session_id,
        artifact_type=body.artifact_type,
        title=title,
        content=content,
        sanitized_html=sanitized,
        word_count=word_count,
        sources=[s.model_dump() for s in sources],
    )
    db.add(artifact)
    await db.flush()
    await db.refresh(artifact)

    return ArtifactResponse(
        id=artifact.id,
        session_id=body.session_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        content=artifact.content,
        sanitized_html=artifact.sanitized_html,
        word_count=artifact.word_count,
        sources=sources,
        created_at=artifact.created_at,
    )


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(artifact_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retrieve a previously generated artifact by ID."""
    result = await db.execute(
        select(DBArtifact).where(DBArtifact.id == artifact_id)
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return ArtifactResponse(
        id=artifact.id,
        session_id=artifact.session_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        content=artifact.content,
        sanitized_html=artifact.sanitized_html,
        word_count=artifact.word_count,
        sources=[SourceChunk(**s) for s in (artifact.sources or [])],
        created_at=artifact.created_at,
    )


@router.get("/session/{session_id}", response_model=list[ArtifactResponse])
async def list_session_artifacts(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all artifacts for a session."""
    result = await db.execute(
        select(DBArtifact)
        .where(DBArtifact.session_id == session_id)
        .order_by(DBArtifact.created_at.desc())
    )
    artifacts = result.scalars().all()
    return [
        ArtifactResponse(
            id=a.id,
            session_id=a.session_id,
            artifact_type=a.artifact_type,
            title=a.title,
            content=a.content,
            sanitized_html=a.sanitized_html,
            word_count=a.word_count,
            sources=[SourceChunk(**s) for s in (a.sources or [])],
            created_at=a.created_at,
        )
        for a in artifacts
    ]
