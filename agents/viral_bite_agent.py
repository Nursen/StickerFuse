"""Agent that extracts viral bites from a subtopic — the specific quotes, phrases,
and meme concepts that would make monetizable sticker designs.

Usage:
  python -m agents.viral_bite_agent "Eras Tour final show" --context "Taylor Swift"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.viral import ViralBiteCollection
from utils.llm_retry import sync_retry_llm

load_dotenv()
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """\
You are a viral content curator specializing in identifying monetizable moments from internet culture.

Given a trending subtopic and optional raw social media data, extract the specific VIRAL BITES —
the exact quotes, catchphrases, lyrics, hashtags, or meme texts that people are repeating,
remixing, and sharing.

For each viral bite, assess its monetization potential for sticker designs:
- HIGH: universally recognizable phrase, strong visual potential, broad appeal
- MEDIUM: popular within a niche community, good for targeted merch
- LOW: too niche or too fleeting to sell well

Be specific and exact — quote the actual text people are using, not paraphrases.
Include the cultural context so a designer understands the reference.\

CRITICAL QUALITY BAR:
- Prefer EVENT-LEVEL moments (who did what, where/when) over generic topic words.
- Reject generic fragments like "stage", "vibe", "performance", "festival", "technical issue" unless tied to a concrete incident.
- Each bite must be understandable as a standalone moment and include a concrete hook.
- If a candidate is too vague, replace it with a more specific one.
"""


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(DEFAULT_MODEL, provider=provider)


viral_bite_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=ViralBiteCollection,
)


def extract_viral_bites(
    subtopic: str,
    context: str = "",
    raw_data: dict | None = None,
) -> ViralBiteCollection:
    """Extract viral bites from a subtopic."""
    parts = [f"Subtopic: {subtopic}"]
    if context:
        parts.append(f"Parent topic context: {context}")
    if raw_data:
        parts.append(
            f"Raw social media data:\n{json.dumps(raw_data, indent=2, ensure_ascii=False)}"
        )
    parts.append(
        "Extract 4-6 viral bites from this subtopic that would make great sticker designs."
    )

    result = sync_retry_llm(lambda: viral_bite_agent.run_sync("\n\n".join(parts)))
    return result.output


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract viral bites from a subtopic")
    parser.add_argument("subtopic", help="Trending subtopic to mine for viral bites")
    parser.add_argument("--context", default="", help="Parent topic for context")
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    print(f"Extracting viral bites from: {args.subtopic}")
    result = extract_viral_bites(args.subtopic, context=args.context)

    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
