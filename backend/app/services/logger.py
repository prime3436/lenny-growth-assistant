"""
Agent Trajectory Logger — records every LLM interaction with full metadata.
Required by the assignment spec: "Agent transcripts / logs"
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LOGS_DIR = Path(__file__).parent.parent.parent / "logs" / "agent_trajectories"


def _ensure_logs_dir() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR


def log_trajectory(
    *,
    session_id: uuid.UUID,
    turn_index: int,
    query: str,
    response: str,
    provider: str,
    model: str,
    sources: list[dict],
    latency_ms: float,
    artifact_type: Optional[str] = None,
    topic: Optional[str] = None,
    word_count: Optional[int] = None,
    stream: bool = False,
) -> Path:
    """
    Append a single agent turn to the session's trajectory log (JSONL format).
    Each session gets its own log file: logs/agent_trajectories/<session_id>.jsonl
    """
    logs_dir = _ensure_logs_dir()
    log_file = logs_dir / f"{session_id}.jsonl"

    entry = {
        "turn": turn_index,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": str(session_id),
        "provider": provider,
        "model": model,
        "stream": stream,
        "latency_ms": round(latency_ms, 2),
        "query": query,
        "response_preview": response[:300] + ("…" if len(response) > 300 else ""),
        "response_length": len(response),
        "sources_count": len(sources),
        "sources": [
            {
                "episode": s.get("episode_title", ""),
                "guest": s.get("guest", ""),
                "score": s.get("score", 0),
            }
            for s in sources
        ],
    }

    if artifact_type:
        entry["artifact_type"] = artifact_type
        entry["artifact_topic"] = topic
        entry["artifact_word_count"] = word_count

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    logger.info(
        f"[trajectory] session={str(session_id)[:8]}… turn={turn_index} "
        f"provider={provider}/{model} latency={latency_ms:.0f}ms sources={len(sources)}"
    )
    return log_file


def get_session_trajectory(session_id: uuid.UUID) -> list[dict]:
    """Load full trajectory log for a session."""
    log_file = LOGS_DIR / f"{session_id}.jsonl"
    if not log_file.exists():
        return []
    entries = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def list_all_sessions() -> list[dict]:
    """List all logged sessions with summary stats."""
    logs_dir = _ensure_logs_dir()
    summaries = []
    for log_file in sorted(logs_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True):
        entries = []
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if entries:
            summaries.append({
                "session_id": log_file.stem,
                "turns": len(entries),
                "first_query": entries[0].get("query", "")[:80],
                "last_activity": entries[-1].get("timestamp"),
                "models_used": list({e.get("model") for e in entries}),
                "avg_latency_ms": round(
                    sum(e.get("latency_ms", 0) for e in entries) / len(entries), 1
                ),
            })
    return summaries
