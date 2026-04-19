"""Agent that generates sticker design concepts from a viral bite.

Usage:
  python -m agents.sticker_idea_agent "I'm the problem, it's me"
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

from schemas.sticker import StickerIdeaSet

load_dotenv()
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """\
You are a creative director for a sticker design studio that turns viral internet moments into
sellable merchandise. You understand both internet culture AND visual design.

Given a viral bite (a quote, catchphrase, lyric, or meme concept), generate 3-5 distinct sticker
concepts. Each concept should be a different creative interpretation:

- Vary the art styles (kawaii, retro, minimalist, hand-lettered, pop-art, grunge, watercolor, pixel-art)
- Vary the layouts (text-only, image-only, text-and-image)
- Think about what would look good as a 3-inch die-cut sticker on a laptop or water bottle
- Consider what sells on Redbubble and Etsy — clean designs, readable text, strong silhouettes

For text-only stickers, focus on typography and lettering style.
For image stickers, describe the visual in enough detail for an AI image generator.
For text+image combos, describe how text and image interact.

Suggest specific color palettes that match the vibe of the viral moment.\
"""


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(DEFAULT_MODEL, provider=provider)


sticker_idea_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=StickerIdeaSet,
)


def generate_sticker_ideas(
    viral_bite: str,
    context: str = "",
) -> StickerIdeaSet:
    """Generate sticker concepts from a viral bite."""
    parts = [f'Viral bite: "{viral_bite}"']
    if context:
        parts.append(f"Cultural context: {context}")
    parts.append("Generate 3-5 distinct sticker design concepts for this viral moment.")

    result = sticker_idea_agent.run_sync("\n\n".join(parts))
    return result.output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sticker ideas from a viral bite")
    parser.add_argument("viral_bite", help="The viral text/phrase to design stickers for")
    parser.add_argument("--context", default="", help="Cultural context")
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    print(f'Generating sticker ideas for: "{args.viral_bite}"')
    result = generate_sticker_ideas(args.viral_bite, context=args.context)

    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
