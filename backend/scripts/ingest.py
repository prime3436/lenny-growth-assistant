"""
Standalone ingestion script — run to pre-populate the transcript cache.

Usage:
    python scripts/ingest.py [--force] [--max N]

Options:
    --force   Re-download even if cached
    --max N   Limit to N episodes (useful for testing)
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.ingestion import ingest_transcripts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Lenny's Podcast transcripts")
    parser.add_argument("--force", action="store_true", help="Re-download all transcripts")
    parser.add_argument("--max", type=int, default=None, help="Max episodes to process")
    args = parser.parse_args()

    settings = get_settings()

    target_dir = settings.resolved_transcripts_dir
    logger.info(f"Starting ingestion → {target_dir}")
    chunks = ingest_transcripts(
        data_dir=target_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        max_episodes=args.max,
        force_refresh=args.force,
    )
    logger.info(f"✅ Done: {len(chunks)} chunks from transcripts in {target_dir}")
