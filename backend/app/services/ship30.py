"""
Ship 30 for 30 Essay Generation Skill.

Generates ~1,250-word atomic essays following Ship 30 for 30 principles:
  - Strong hook (first line must stop the scroll)
  - Clear "big idea" statement
  - 3-5 insight sections with skimmable bold callouts
  - Concrete examples grounded in Lenny's transcript context
  - Actionable takeaway / CTA
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.services.rag import retrieve, format_context
from app.services.llm import get_provider
from app.models.schemas import SourceChunk

logger = logging.getLogger(__name__)


SHIP30_SYSTEM = """You are a world-class writer trained in the Ship 30 for 30 framework.
You write atomic essays that are punchy, skimmable, and genuinely useful.

Your essays follow this structure:
1. **Hook** (1 sentence): Start with a counterintuitive statement, bold claim, or provocative question. Never start with "I".
2. **Setup** (2-3 sentences): Context — why this topic matters right now.
3. **Big Idea** (1 sentence, bolded): The core insight in one line.
4. **Body** (3-5 sections):
   - Each section has a **bolded callout** as a mini-headline
   - 3-5 sentences of insight per section
   - Use bullet points sparingly — max 1 list per essay
5. **Conclusion / CTA** (2-3 sentences): What should the reader do Monday morning?

Style rules:
- Short paragraphs (2-4 sentences max)
- No jargon without explanation
- Every sentence must earn its place
- Ground insights in the provided transcript context (cite episodes)
- Target: ~1,250 words

Do NOT add a title header — the caller will handle the title."""


SHIP30_USER_TEMPLATE = """Write a Ship 30 for 30 atomic essay about: **{topic}**

Use the following Lenny's Podcast transcript context to ground your insights:

{context}

Remember:
- ~1,250 words
- Strong hook first
- Bold the key insight callouts
- Cite specific episodes/guests where relevant
- End with a concrete, actionable takeaway"""


async def generate_ship30_essay(
    topic: str,
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
    top_k: int = 6,
) -> tuple[str, list[SourceChunk]]:
    """
    Generate a Ship 30 for 30 essay on `topic`.

    Returns:
        (essay_markdown: str, sources: list[SourceChunk])
    """
    # 1. Retrieve relevant transcript chunks
    sources = retrieve(topic, top_k=top_k)
    context = format_context(sources)

    # 2. Build prompt
    user_prompt = SHIP30_USER_TEMPLATE.format(topic=topic, context=context)

    # 3. Call LLM
    provider, pname, mname = get_provider(provider_name, model_name)
    logger.info(f"Generating Ship30 essay via {pname}/{mname} | topic: {topic!r}")

    essay = await provider.complete(
        messages=[{"role": "user", "content": user_prompt}],
        system=SHIP30_SYSTEM,
    )

    return essay, sources


def extract_title(essay: str, fallback: str = "Untitled Essay") -> str:
    """
    Extract a title from the first non-empty line of the essay,
    or generate a short title from the first sentence.
    """
    lines = [l.strip() for l in essay.splitlines() if l.strip()]
    if not lines:
        return fallback

    first = lines[0]
    # Strip markdown bold/italic
    first = re.sub(r"[*_#]", "", first).strip()
    # Truncate to ~80 chars
    if len(first) > 80:
        first = first[:77] + "…"
    return first or fallback


def count_words(text: str) -> int:
    return len(text.split())
