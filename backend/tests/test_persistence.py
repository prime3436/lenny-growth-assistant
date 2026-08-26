"""
Persistence integration tests — exercises real database behavior.

These tests run against a dedicated test PostgreSQL database using the same
async engine as production. They cover:
- Table creation and schema validation
- Session / Message / Artifact create-read lifecycle
- Cascade deletes (Session → Messages, Artifacts)
- JSON column serialization for sources

Note: These tests require a live PostgreSQL server. They are automatically
skipped if the DB is unreachable (e.g. CI without Docker).
"""
from __future__ import annotations

import pytest
import uuid

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text


# ── Test DB connection string ────────────────────────────────────────────────
# Defaults to localhost:5432 (works from host machine or docker exec -e override).
# Override via: TEST_DATABASE_URL env var

import os
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://lenny:lenny@localhost:5432/lenny_db",
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def db_engine():
    """Create an async engine per test — function scope matches asyncio event loop scope."""
    from app.models.database import Base
    try:
        engine = create_async_engine(TEST_DB_URL, echo=False, pool_timeout=5)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")


@pytest.fixture
async def db_session(db_engine):
    """Yield a fresh async session per test."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDatabaseSchema:
    """Verify that the schema and tables are created correctly."""

    @pytest.mark.asyncio
    async def test_tables_exist(self, db_session):
        """All three core tables must exist in the database."""
        for table in ("sessions", "messages", "artifacts"):
            result = await db_session.execute(
                text(f"SELECT to_regclass('public.{table}')")
            )
            exists = result.scalar()
            assert exists is not None, f"Table '{table}' does not exist in the DB"


class TestSessionPersistence:
    """Tests for Session model creation and retrieval."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_session(self, db_session):
        """Create a Session and verify it can be read back."""
        from app.models.database import Session as SessionModel

        new_session = SessionModel(
            model_provider="ollama",
            model_name="qwen3:4b",
        )
        db_session.add(new_session)
        await db_session.commit()
        await db_session.refresh(new_session)

        session_id = new_session.id
        assert isinstance(session_id, uuid.UUID)

        stmt = select(SessionModel).where(SessionModel.id == session_id)
        result = await db_session.execute(stmt)
        fetched = result.scalar_one_or_none()

        assert fetched is not None
        assert fetched.model_provider == "ollama"
        assert fetched.model_name == "qwen3:4b"

        # Cleanup
        await db_session.delete(fetched)
        await db_session.commit()


class TestMessagePersistence:
    """Tests for Message creation with sources JSON."""

    @pytest.mark.asyncio
    async def test_create_session_with_messages(self, db_session):
        """Create Session → Messages and verify relationship + JSON sources."""
        from app.models.database import Session as SessionModel, Message

        session = SessionModel(model_provider="ollama", model_name="qwen3:4b")
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # User message with RAG sources (JSON column)
        msg = Message(
            session_id=session.id,
            role="user",
            content="What is product-market fit?",
            model_provider="ollama",
            model_name="qwen3:4b",
            sources=[
                {"episode_title": "PMF Episode", "guest": "Brian Balfour", "score": 12.5}
            ],
        )
        db_session.add(msg)

        # Assistant reply
        reply = Message(
            session_id=session.id,
            role="assistant",
            content="Product-market fit is when...",
            model_provider="ollama",
            model_name="qwen3:4b",
            sources=[],
        )
        db_session.add(reply)
        await db_session.commit()

        # Read back messages via query
        from app.models.database import Message as MessageModel
        result = await db_session.execute(
            select(MessageModel).where(MessageModel.session_id == session.id)
        )
        messages = result.scalars().all()

        assert len(messages) == 2
        user_msg = next(m for m in messages if m.role == "user")
        assert user_msg.content == "What is product-market fit?"
        assert user_msg.sources[0]["guest"] == "Brian Balfour"
        assert user_msg.sources[0]["score"] == 12.5

        # Cleanup
        await db_session.delete(session)
        await db_session.commit()


class TestArtifactPersistence:
    """Tests for Artifact creation and retrieval."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_artifact(self, db_session):
        """Create an Artifact linked to a Session and verify retrieval."""
        from app.models.database import Session as SessionModel, Artifact

        session = SessionModel(model_provider="ollama", model_name="qwen3:4b")
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        art = Artifact(
            session_id=session.id,
            artifact_type="ship30",
            title="Why Startups Fail",
            content="# Why Startups Fail\n\nMost startups fail because...",
            sanitized_html="<h1>Why Startups Fail</h1><p>Most startups fail because...</p>",
            word_count=450,
            sources=[{"episode_title": "PMF Episode", "score": 18.0}],
        )
        db_session.add(art)
        await db_session.commit()
        await db_session.refresh(art)

        from app.models.database import Artifact as ArtifactModel
        result = await db_session.execute(
            select(ArtifactModel).where(ArtifactModel.session_id == session.id)
        )
        fetched_art = result.scalar_one_or_none()

        assert fetched_art is not None
        assert fetched_art.title == "Why Startups Fail"
        assert fetched_art.word_count == 450
        assert fetched_art.artifact_type == "ship30"
        assert fetched_art.sources[0]["score"] == 18.0

        # Cleanup
        await db_session.delete(session)
        await db_session.commit()


class TestCascadeDelete:
    """Verify cascade behavior: deleting Session removes all children."""

    @pytest.mark.asyncio
    async def test_cascade_delete_removes_messages_and_artifacts(self, db_session):
        """Deleting a Session must cascade-delete all Messages and Artifacts."""
        from app.models.database import Session as SessionModel, Message, Artifact

        session = SessionModel(model_provider="ollama", model_name="qwen3:4b")
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)
        session_id = session.id

        msg = Message(session_id=session_id, role="user", content="test", sources=[])
        art = Artifact(
            session_id=session_id,
            artifact_type="ship30",
            title="Test",
            content="test",
            word_count=1,
        )
        db_session.add_all([msg, art])
        await db_session.commit()

        # Delete parent
        await db_session.delete(session)
        await db_session.commit()

        from app.models.database import Message as MessageModel, Artifact as ArtifactModel
        msgs = (await db_session.execute(
            select(MessageModel).where(MessageModel.session_id == session_id)
        )).scalars().all()
        arts = (await db_session.execute(
            select(ArtifactModel).where(ArtifactModel.session_id == session_id)
        )).scalars().all()

        assert len(msgs) == 0, f"Expected 0 messages after cascade delete, got {len(msgs)}"
        assert len(arts) == 0, f"Expected 0 artifacts after cascade delete, got {len(arts)}"
