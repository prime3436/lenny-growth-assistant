"""
Transcript ingestion pipeline.

Fetches transcripts from the ChatPRD/lennys-podcast-transcripts GitHub repo,
parses YAML front-matter + body text, and chunks them for BM25 indexing.
"""
from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Iterator
import requests
import yaml

logger = logging.getLogger(__name__)

# GitHub API endpoint for the transcripts repo
# Structure: episodes/<guest-name>/transcript.md
REPO_API = "https://api.github.com/repos/ChatPRD/lennys-podcast-transcripts/contents/episodes"
RAW_BASE  = "https://raw.githubusercontent.com/ChatPRD/lennys-podcast-transcripts/main/episodes"


# ── Data structures ───────────────────────────────────────────────────────────

class TranscriptChunk:
    __slots__ = ("episode_title", "episode_number", "guest", "chunk_text", "chunk_index")

    def __init__(
        self,
        episode_title: str,
        episode_number: str,
        guest: str,
        chunk_text: str,
        chunk_index: int,
    ):
        self.episode_title = episode_title
        self.episode_number = episode_number
        self.guest = guest
        self.chunk_text = chunk_text
        self.chunk_index = chunk_index

    def to_dict(self) -> dict:
        return {
            "episode_title": self.episode_title,
            "episode_number": self.episode_number,
            "guest": self.guest,
            "chunk_text": self.chunk_text,
            "chunk_index": self.chunk_index,
        }


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Split YAML front-matter from body. Returns (meta, body)."""
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                return meta, parts[2].strip()
            except yaml.YAMLError:
                pass
    return {}, raw


def _clean_text(text: str) -> str:
    """Remove transcript artifacts (timestamps, speaker labels, etc.)."""
    # Remove timestamps like [00:01:23]
    text = re.sub(r"\[\d{2}:\d{2}:\d{2}\]", "", text)
    # Remove speaker labels like "Lenny:" or "Guest (John):"
    text = re.sub(r"^[A-Za-z ]+(?:\([^)]+\))?:\s*", "", text, flags=re.MULTILINE)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping word-count chunks."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


# ── Fetching ──────────────────────────────────────────────────────────────────

def _list_transcript_files() -> list[str]:
    """
    List all episode slugs from the repo.
    Structure: episodes/<guest-slug>/transcript.md
    Returns list of slugs (e.g. 'ada-chen-rekhi').
    """
    try:
        resp = requests.get(REPO_API, timeout=15,
                            headers={"Accept": "application/vnd.github+json"})
        resp.raise_for_status()
        # Each entry is a directory (episode slug), not a .md file
        slugs = [f["name"] for f in resp.json() if f["type"] == "dir"]
        logger.info(f"Found {len(slugs)} episode folders on GitHub")
        return slugs
    except Exception as e:
        logger.error(f"Failed to list episode folders: {e}")
        return []


def _fetch_raw_transcript(slug: str) -> str | None:
    """Fetch raw content of transcript.md inside an episode folder."""
    url = f"{RAW_BASE}/{slug}/transcript.md"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch transcript for {slug}: {e}")
        return None


# ── Local cache ───────────────────────────────────────────────────────────────

def _load_local_transcripts(data_dir: str) -> Iterator[tuple[str, str]]:
    """Load already-downloaded .md files from local disk."""
    p = Path(data_dir)
    for f in p.glob("*.md"):
        yield f.name, f.read_text(encoding="utf-8")


def _save_transcript(data_dir: str, filename: str, content: str) -> None:
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    (Path(data_dir) / filename).write_text(content, encoding="utf-8")


# ── Main ingestion entry point ────────────────────────────────────────────────

def ingest_transcripts(
    data_dir: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    max_episodes: int | None = None,
    force_refresh: bool = False,
) -> list[TranscriptChunk]:
    """
    Full ingestion pipeline:
      1. Check local cache; fetch from GitHub if needed.
      2. Parse front-matter + body.
      3. Chunk and return all TranscriptChunk objects.
    """
    local_files = {f: c for f, c in _load_local_transcripts(data_dir)}
    logger.info(f"Found {len(local_files)} locally cached transcripts")

    if force_refresh or len(local_files) == 0:
        remote_slugs = _list_transcript_files()
        for slug in remote_slugs[:max_episodes]:
            cache_name = f"{slug}.md"
            if cache_name not in local_files or force_refresh:
                content = _fetch_raw_transcript(slug)
                if content:
                    _save_transcript(data_dir, cache_name, content)
                    local_files[cache_name] = content
        logger.info(f"After fetch: {len(local_files)} transcripts cached")

    all_chunks: list[TranscriptChunk] = []
    for filename, raw in local_files.items():
        meta, body = _parse_frontmatter(raw)
        body = _clean_text(body)
        if not body:
            continue

        episode_title = str(meta.get("title", filename.replace(".md", "").replace("-", " ")))
        episode_number = str(meta.get("episode", meta.get("ep", "")))
        guest = str(meta.get("guest", meta.get("interviewee", "")))

        chunks = _chunk_text(body, chunk_size=chunk_size, overlap=chunk_overlap)
        for i, chunk in enumerate(chunks):
            all_chunks.append(
                TranscriptChunk(
                    episode_title=episode_title,
                    episode_number=episode_number,
                    guest=guest,
                    chunk_text=chunk,
                    chunk_index=i,
                )
            )

    logger.info(f"Ingestion complete: {len(all_chunks)} chunks from {len(local_files)} episodes")
    return all_chunks
