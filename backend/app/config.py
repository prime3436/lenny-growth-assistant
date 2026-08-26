"""
Application configuration — reads from .env file.
"""
from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me"

    # Database
    database_url: str = "postgresql+asyncpg://lenny:lenny@localhost:5432/lenny_db"

    # LLM
    llm_provider: Literal["anthropic", "openai", "ollama"] = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    claude_model: str = "claude-3-5-sonnet-20241022"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # RAG
    transcripts_dir: str = "../data/transcripts"
    bm25_top_k: int = 5
    chunk_size: int = 500
    chunk_overlap: int = 50

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8080,http://127.0.0.1:5500"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def resolved_transcripts_dir(self) -> str:
        """Dynamically resolve transcript directory across local dev, repo root, or Docker container."""
        from pathlib import Path
        candidate = Path(self.transcripts_dir)
        if candidate.is_dir():
            return str(candidate)
        # Check relative to backend/
        backend_rel = Path(__file__).resolve().parent.parent.parent / "data" / "transcripts"
        if backend_rel.is_dir():
            return str(backend_rel)
        # Check docker container default
        container_path = Path("/app/data/transcripts")
        if container_path.is_dir():
            return str(container_path)
        return self.transcripts_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
