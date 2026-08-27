"""
Chat API — session management + RAG-grounded conversation.
Includes SSE streaming endpoint and agent trajectory logging.
"""
from __future__ import annotations

import json
import time
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.db.session import get_db
from app.models.database import Session as DBSession, Message as DBMessage
from app.models.schemas import (
    SessionCreate, SessionResponse, SessionSummary,
    ChatRequest, ChatResponse,
    ModelSwitchRequest, ModelSwitchResponse,
    ChatMessage,
)
from app.services.rag import retrieve, format_context
from app.services.llm import get_provider, SYSTEM_PROMPT
from app.services.logger import log_trajectory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation session."""
    from app.services.llm import get_provider
    from app.config import get_settings
    s = get_settings()

    provider_name = s.llm_provider
    model_name = s.claude_model if provider_name == "anthropic" else (
        s.openai_model if provider_name == "openai" else s.ollama_model
    )

    session = DBSession(
        model_provider=provider_name,
        model_name=model_name,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List saved conversations, newest activity first."""
    first_user_message = (
        select(DBMessage.content)
        .where(DBMessage.session_id == DBSession.id, DBMessage.role == "user")
        .order_by(DBMessage.created_at)
        .limit(1)
        .scalar_subquery()
    )
    message_count = (
        select(func.count(DBMessage.id))
        .where(DBMessage.session_id == DBSession.id)
        .scalar_subquery()
    )
    last_message_at = (
        select(func.max(DBMessage.created_at))
        .where(DBMessage.session_id == DBSession.id)
        .scalar_subquery()
    )
    result = await db.execute(
        select(DBSession, first_user_message, message_count)
        .order_by(last_message_at.desc().nulls_last(), DBSession.created_at.desc())
    )
    return [
        SessionSummary(
            id=session.id,
            created_at=session.created_at,
            model_provider=session.model_provider,
            model_name=session.model_name,
            # Artifact-only sessions have no user message. Their topic is saved
            # as metadata so the history never falls back to an anonymous label.
            title=(title or (session.user_metadata or {}).get("title") or "New conversation").strip()[:80],
            message_count=count,
        )
        for session, title, count in result.all()
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get session metadata."""
    result = await db.execute(select(DBSession).where(DBSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get full conversation history for a session."""
    result = await db.execute(
        select(DBMessage)
        .where(DBMessage.session_id == session_id)
        .order_by(DBMessage.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Send a message and get a RAG-grounded response.
    Maintains multi-turn context via session history.
    """
    # 1. Load session
    result = await db.execute(select(DBSession).where(DBSession.id == body.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Load conversation history (last 10 turns for context window)
    history_result = await db.execute(
        select(DBMessage)
        .where(DBMessage.session_id == body.session_id)
        .order_by(DBMessage.created_at.desc())
        .limit(10)
    )
    history = list(reversed(history_result.scalars().all()))

    # 3. Retrieve relevant transcript chunks
    sources = retrieve(body.message, top_k=5)
    context = format_context(sources)

    # 4. Build messages list for LLM
    system = SYSTEM_PROMPT + f"\n\n## Relevant Transcript Context\n\n{context}"

    messages: list[dict] = []
    for h in history:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": body.message})

    # 5. Get LLM provider (allow per-request override)
    try:
        provider, pname, mname = get_provider(body.model_provider, body.model_name)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 6. Generate response (with latency tracking)
    t0 = time.monotonic()
    try:
        answer = await provider.complete(messages=messages, system=system)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"LLM error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="LLM request failed")
    latency_ms = (time.monotonic() - t0) * 1000

    # 7. Persist user + assistant messages
    now = datetime.now(timezone.utc)
    user_msg = DBMessage(
        session_id=body.session_id,
        role="user",
        content=body.message,
        model_provider=pname,
        model_name=mname,
        sources=[],
        created_at=now,
    )
    sources_dicts = [s.model_dump() for s in sources]
    assistant_msg = DBMessage(
        session_id=body.session_id,
        role="assistant",
        content=answer,
        model_provider=pname,
        model_name=mname,
        sources=sources_dicts,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    # 8. Log agent trajectory
    turn_count = len(history) // 2 + 1
    log_trajectory(
        session_id=body.session_id,
        turn_index=turn_count,
        query=body.message,
        response=answer,
        provider=pname,
        model=mname,
        sources=sources_dicts,
        latency_ms=latency_ms,
        stream=False,
    )

    return ChatResponse(
        session_id=body.session_id,
        message_id=assistant_msg.id,
        answer=answer,
        sources=sources,
        model_provider=pname,
        model_name=mname,
        created_at=assistant_msg.created_at,
    )


# ── Streaming chat ────────────────────────────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    SSE streaming endpoint — tokens are pushed as they are generated.
    Frontend receives: data: {"token": "..."}\n\n
    Final event:       data: {"done": true, "sources": [...]}\n\n
    """
    result = await db.execute(select(DBSession).where(DBSession.id == body.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    history_result = await db.execute(
        select(DBMessage)
        .where(DBMessage.session_id == body.session_id)
        .order_by(DBMessage.created_at.desc())
        .limit(10)
    )
    history = list(reversed(history_result.scalars().all()))

    sources = retrieve(body.message, top_k=5)
    context = format_context(sources)
    system = SYSTEM_PROMPT + f"\n\n## Relevant Transcript Context\n\n{context}"

    messages: list[dict] = [
        {"role": h.role, "content": h.content} for h in history
    ]
    messages.append({"role": "user", "content": body.message})

    try:
        provider, pname, mname = get_provider(body.model_provider, body.model_name)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    sources_dicts = [s.model_dump() for s in sources]

    async def event_generator():
        full_response = ""
        t0 = time.monotonic()
        try:
            async for token in provider.stream_complete(messages=messages, system=system):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except RuntimeError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        latency_ms = (time.monotonic() - t0) * 1000

        # Persist messages
        async with db as active_db:
            user_msg = DBMessage(
                session_id=body.session_id, role="user",
                content=body.message, model_provider=pname,
                model_name=mname, sources=[], created_at=datetime.now(timezone.utc),
            )
            assistant_msg = DBMessage(
                session_id=body.session_id, role="assistant",
                content=full_response, model_provider=pname,
                model_name=mname, sources=sources_dicts,
            )
            active_db.add(user_msg)
            active_db.add(assistant_msg)
            await active_db.flush()

        # Log trajectory
        turn_count = len(history) // 2 + 1
        log_trajectory(
            session_id=body.session_id,
            turn_index=turn_count,
            query=body.message,
            response=full_response,
            provider=pname, model=mname,
            sources=sources_dicts,
            latency_ms=latency_ms,
            stream=True,
        )

        # Done event with sources
        yield f"data: {json.dumps({'done': True, 'sources': sources_dicts, 'model_provider': pname, 'model_name': mname})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Agent trajectory viewer ───────────────────────────────────────────────────

@router.get("/trajectories")
async def list_trajectories():
    """List all logged agent sessions with summary stats."""
    from app.services.logger import list_all_sessions
    return list_all_sessions()


@router.get("/trajectories/{session_id}")
async def get_trajectory(session_id: uuid.UUID):
    """Get the full agent trajectory for a session."""
    from app.services.logger import get_session_trajectory
    entries = get_session_trajectory(session_id)
    if not entries:
        raise HTTPException(status_code=404, detail="No trajectory found for this session")
    return {"session_id": str(session_id), "turns": len(entries), "trajectory": entries}


# ── Model switching ───────────────────────────────────────────────────────────

@router.post("/models/switch", response_model=ModelSwitchResponse)
async def switch_model(body: ModelSwitchRequest):
    """Switch the active LLM provider (takes effect for subsequent requests)."""
    from app.config import get_settings
    import app.services.llm as llm_module
    s = get_settings()

    # Determine default model for provider
    if body.provider == "anthropic":
        mname = body.model_name or s.claude_model
    elif body.provider == "openai":
        mname = body.model_name or s.openai_model
    else:
        mname = body.model_name or s.ollama_model

    # Try to build and health-check the provider
    try:
        from app.services.llm import build_provider
        prov = build_provider(body.provider, mname)
        ok = await prov.health_check()
    except (ValueError, RuntimeError) as e:
        return ModelSwitchResponse(
            provider=body.provider,
            model_name=mname,
            status="error",
            message=str(e),
        )

    # Reset cached singleton
    llm_module._current_provider = prov
    llm_module._current_provider_name = body.provider
    llm_module._current_model_name = mname

    return ModelSwitchResponse(
        provider=body.provider,
        model_name=mname,
        status="ok" if ok else "warning",
        message="Switched successfully" if ok else f"Provider reachable but health check failed for {mname}",
    )


@router.get("/models/current")
async def current_model():
    """Get the currently active model."""
    import app.services.llm as llm_module
    from app.config import get_settings
    s = get_settings()
    return {
        "provider": llm_module._current_provider_name or s.llm_provider,
        "model": llm_module._current_model_name or "default",
    }
