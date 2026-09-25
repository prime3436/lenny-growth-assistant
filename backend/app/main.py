"""
FastAPI application entry point.
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.logging import RichHandler

from app.config import get_settings
from app.db.session import engine
from app.models.database import Base
from app.api import health, chat, artifacts, settings as settings_api
from app.services import rag as rag_service


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("lenny")

settings = get_settings()



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Lenny Growth Assistant starting up…")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables ready")

    n = rag_service.build_index()
    logger.info(f"✅ BM25 index ready: {n} chunks")

    yield

    logger.info("👋 Shutting down…")
    await engine.dispose()



app = FastAPI(
    title="Lenny Growth Assistant",
    description="RAG-powered conversational assistant grounded in Lenny's Podcast transcripts",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(artifacts.router)
app.include_router(settings_api.router)
