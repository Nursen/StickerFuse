"""Listing generator agent -- creates optimized Redbubble/Etsy product listings.

Generates SEO-optimized titles, descriptions, tags, and pricing for print-on-demand
sticker listings. Produces 2-3 variations per concept for A/B testing different
keyword strategies.

Uses Gemini Flash-Lite (cheap -- this is just text generation, no comprehension needed).

Usage:
  python -m agents.listing_generator "Bridgerton bee with 'let him cook'"
  python -m agents.listing_generator "cat programmer" --fandom "tech humor" --style "kawaii"
  python -m agents.listing_generator "cottagecore mushroom" --platform etsy
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Flash-Lite -- cheap, just generating text
LISTING_MODEL = os.getenv("GEMINI_MODEL_LITE", "gemini-2.0-flash-lite")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProductListing(BaseModel):
    title: str = Field(description="SEO-optimized title, <140 chars, includes key search terms")
    description: str = Field(description="Engaging product description, 150-300 words, keyword-rich but natural")
    tags: list[str] = Field(description="13 tags for Redbubble (their limit), mix of broad and specific")
    category: str = Field(description="Best Redbubble category for this sticker")
    suggested_price_usd: float = Field(description="Suggested retail price based on market research")
    seo_notes: str = Field(description="Why these keywords were chosen -- what people search for")


class ListingSet(BaseModel):
    sticker_concept: str
    listings: list[ProductListing] = Field(description="2-3 listing variations (different keyword strategies)")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a Redbubble/Etsy SEO expert who writes product listings that rank and convert. \
You understand how print-on-demand marketplace search works and craft listings that \
balance discoverability with personality.

## REDBUBBLE SEO RULES

- **Titles**: Lead with the most-searched terms. Format: "[Primary keyword] - [Secondary keyword] \
  | [Fandom/Niche] [Product type]". Keep under 140 characters.
- **Tags**: Exactly 13 tags (Redbubble's limit). Mix of:
  - 3-4 broad tags ("funny sticker", "laptop sticker", "water bottle sticker", "vinyl sticker")
  - 3-4 niche tags ("bridgerton sticker", "regency era", "period drama fan")
  - 3-4 specific tags ("viscount rizz", "I burn for you", "whistledown vibes")
  - 1-2 occasion tags ("gift for her", "bookish gift", "fandom gift")
- **Descriptions**: 150-300 words. Must include:
  - Hook line (what makes this sticker special)
  - Who it's for (the target buyer persona)
  - Material/quality details (vinyl, waterproof, dishwasher safe, UV resistant)
  - Size info (standard sticker sizes: 3", 4", 5.5")
  - Use cases (laptop, water bottle, notebook, phone case, car bumper)
  - Gift occasions (birthday, holiday, just because, self-purchase)
  - Natural keyword integration (don't stuff, weave them in)
- **Pricing**: Standard Redbubble stickers $2.50-$5.00. Premium/detailed designs $4-6. \
  Sticker packs $8-12. Factor in Redbubble's margin (they take ~50%).

## ETSY DIFFERENCES (when platform = etsy)

- Titles can be longer (140 chars), front-load keywords even more aggressively
- 13 tags, each up to 20 characters
- Descriptions should mention "handmade" or "designed by independent artist"
- Pricing can be slightly higher ($3-7 for singles, $10-15 for packs)
- Include shipping/processing time language

## A/B TESTING STRATEGY

Generate 2-3 listing variations with DIFFERENT keyword strategies:
1. **Broad reach**: Generic keywords that cast a wide net ("funny sticker", "meme sticker")
2. **Niche targeted**: Fandom-specific keywords ("bridgerton fan gift", "regency era sticker")
3. **Long-tail**: Very specific phrases people search ("I burn for you bridgerton sticker")

Each variation should have a different title, tags, and description approach.\
"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(LISTING_MODEL, provider=provider)


listing_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=ListingSet,
    model_settings=GoogleModelSettings(temperature=0.6, max_tokens=4096),
)


def generate_listings(
    sticker_concept: str,
    fandom: str = "",
    art_style: str = "",
    target_platform: str = "redbubble",
) -> ListingSet:
    """Generate optimized product listings for a sticker concept.

    Args:
        sticker_concept: What the sticker is (e.g. "Bridgerton bee with 'let him cook' text").
        fandom: Parent fandom or topic (e.g. "Bridgerton", "anime", "tech humor").
        art_style: Visual style (e.g. "kawaii", "retro", "minimalist", "watercolor").
        target_platform: "redbubble" or "etsy".
    """
    parts = [f"Sticker concept: {sticker_concept}"]

    if fandom:
        parts.append(f"Fandom/niche: {fandom}")
    if art_style:
        parts.append(f"Art style: {art_style}")

    parts.append(f"Target platform: {target_platform}")
    parts.append(
        "\nGenerate 2-3 listing variations with different keyword strategies "
        "(broad reach, niche targeted, long-tail). Each should have unique titles, "
        "tags, and description angles."
    )

    from utils.llm_retry import sync_retry_llm
    result = sync_retry_llm(lambda: listing_agent.run_sync("\n".join(parts)))
    return result.output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate optimized Redbubble/Etsy product listings for stickers"
    )
    parser.add_argument("concept", help="What the sticker is")
    parser.add_argument("--fandom", default="", help="Parent fandom/topic")
    parser.add_argument("--style", default="", help="Art style (kawaii, retro, etc.)")
    parser.add_argument("--platform", default="redbubble", choices=["redbubble", "etsy"])
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    print(f"Generating listings for: {args.concept}")
    print(f"Platform: {args.platform}")
    result = generate_listings(args.concept, fandom=args.fandom, art_style=args.style, target_platform=args.platform)

    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
