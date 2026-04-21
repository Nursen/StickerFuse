"""Merch ideation agent — finds the collision between fandom DNA and internet culture.

This is the creative core of StickerFuse. Instead of trend-scoring or moment-detecting,
this agent thinks like a merch designer: "What would a fan of [X] actually PUT ON THEIR
LAPTOP?"

The magic formula:
  [fandom visual/character/quote] × [trending internet phrase/meme format] = sticker gold

Uses Gemini with web search grounding to pull both fandom knowledge AND current internet
vernacular, then finds the witty intersections.

Usage:
  python -m agents.merch_ideation_agent "Bridgerton"
  python -m agents.merch_ideation_agent "Minecraft" --vibe "ironic"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.builtin_tools import WebSearchTool
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FandomDNA(BaseModel):
    """The iconic elements of a fandom that fans would recognize on a sticker."""
    iconic_quotes: list[str] = Field(description="Catchphrases, one-liners, quotes fans repeat (e.g. 'I burn for you')")
    ship_names: list[str] = Field(description="Fan ship names and pairings (e.g. 'Kanthony', 'Polin')")
    visual_icons: list[str] = Field(description="Visual symbols fans recognize (e.g. 'the Bridgerton bee', 'the diamond tiara')")
    character_archetypes: list[str] = Field(description="Character traits that became memes (e.g. 'Colin being oblivious', 'Benedict the artist')")
    running_jokes: list[str] = Field(description="Community in-jokes and recurring humor")
    aesthetic_elements: list[str] = Field(description="The visual aesthetic of this fandom (e.g. 'Regency era pastels', 'empire waist dresses')")


class StickerMashup(BaseModel):
    """A single sticker concept born from fandom × internet culture collision."""
    concept: str = Field(description="The sticker idea in one line")
    fandom_element: str = Field(description="What fandom reference this uses")
    internet_element: str = Field(description="What current internet phrase/meme/format this mashes with")
    why_its_funny: str = Field(description="Why this collision works — the joke, the contrast, the recognition")
    text_on_sticker: str | None = Field(description="Exact text that would appear on the sticker (None if image-only)")
    visual_description: str = Field(description="What the sticker looks like — specific enough for image generation")
    category: Literal["quote_mashup", "character_meme", "ship_name", "visual_pun", "identity_statement", "anachronism", "inside_joke"] = Field(
        description="What type of creative collision this is"
    )
    estimated_appeal: Literal["broad", "fandom", "deep_cut"] = Field(
        description="broad = anyone would get it, fandom = fans only, deep_cut = hardcore fans"
    )


class MerchIdeationResult(BaseModel):
    """Output of the merch ideation agent."""
    topic: str
    fandom_dna: FandomDNA
    current_internet_vernacular: list[str] = Field(
        description="The trending internet phrases, formats, and meme templates used in mashups"
    )
    sticker_ideas: list[StickerMashup] = Field(
        description="12-15 sticker concepts, mix of broad appeal and deep cuts"
    )
    recommended_pack: list[str] = Field(
        description="Top 5 sticker concepts that would work as a themed pack"
    )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """\
You are a merch designer who creates stickers for internet-native fandoms. You have two \
superpowers: deep knowledge of fandom culture (quotes, ships, icons, in-jokes) AND fluency \
in current internet vernacular (trending phrases, meme formats, Gen Z slang).

Your job is to find the COLLISION POINTS — where a fandom reference meets an internet phrase \
and creates something that makes a fan laugh and think "I NEED that on my water bottle."

## The Formula

[fandom-specific visual/character/quote] × [trending internet phrase/format] = sticker gold

Examples of great collisions:
- Regency lady in a bonnet + "very demure, very mindful" = anachronism humor
- Penelope/Whistledown + "I'm the problem, it's me" = character × lyric
- Benedict boxing + "he's just like me fr" = character meme
- "I burn for you" in modern bubble letter font = classic quote × modern aesthetic
- A Bridgerton bee + "let him cook" = visual pun × internet phrase
- "Kanthony forever" in Regency script = ship identity statement

## What Makes Merch SELL

1. **Recognition flash** — fan sees it and instantly gets the reference
2. **Identity signal** — wearing/displaying it says "I'm part of THIS group"
3. **Humor** — the collision between high culture and internet speak is inherently funny
4. **Quotability** — people read it and want to say it out loud
5. **Visual clarity** — reads from 3 feet away on a laptop

## What to Generate

For any fandom topic:
1. First, extract the FANDOM DNA — the iconic quotes, ship names, visual icons, \
   character archetypes, running jokes, and aesthetic
2. Then, identify CURRENT INTERNET VERNACULAR that could collide with it — trending \
   phrases, meme templates, Gen Z slang, viral audio references
3. Generate 12-15 sticker concepts spanning:
   - 3-4 broad appeal (anyone who's seen the show would get it)
   - 5-6 fandom level (active fans would love it)
   - 3-4 deep cuts (hardcore fans / subreddit regulars)
   - Mix of: quote mashups, character memes, ship names, visual puns, identity statements

Use the web_search tool to look up:
- Current trending phrases and meme formats (what's hot on TikTok/Twitter RIGHT NOW)
- Fandom-specific references (what fans are saying on Reddit, Tumblr, TikTok)
- Existing popular merch for this fandom (what's already selling, so we can differentiate)

Be SPECIFIC with visual descriptions. "A Regency-era lady looking at her phone with \
a shocked expression" is better than "funny character."

CRITICAL: The text_on_sticker field should be the EXACT text. Keep it SHORT (1-6 words \
ideal, 10 max). Sticker text must be readable at small sizes.\
"""


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(DEFAULT_MODEL, provider=provider)


merch_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=MerchIdeationResult,
    model_settings=GoogleModelSettings(temperature=0.8, max_tokens=8192),
    builtin_tools=[WebSearchTool()],
)


def ideate_merch(
    topic: str,
    vibe: str = "",
    community_context: str = "",
) -> MerchIdeationResult:
    """Generate sticker concepts for a fandom topic.

    Args:
        topic: The fandom/cultural topic (e.g. "Bridgerton", "Minecraft", "Taylor Swift")
        vibe: Optional tone preference ("ironic", "wholesome", "unhinged", "minimalist")
        community_context: Optional extra context from Reddit comments, etc.
    """
    parts = [f'Fandom/topic: "{topic}"']

    if vibe:
        parts.append(f"Preferred vibe/tone: {vibe}")

    if community_context:
        parts.append(
            f"Community context (what fans are currently talking about):\n{community_context}"
        )

    parts.append(
        "Use web search to find:\n"
        "1. Current trending internet phrases and meme formats\n"
        "2. This fandom's most iconic quotes, ships, and visual elements\n"
        "3. What merch already exists (so we can be different)\n\n"
        "Then generate 12-15 sticker concepts that collide fandom references with "
        "internet culture. Mix broad appeal, fandom-level, and deep cuts."
    )

    from utils.llm_retry import sync_retry_llm
    result = sync_retry_llm(lambda: merch_agent.run_sync("\n\n".join(parts)))
    return result.output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate sticker concepts by colliding fandom DNA with internet culture"
    )
    parser.add_argument("topic", help="Fandom or cultural topic (e.g. 'Bridgerton')")
    parser.add_argument("--vibe", default="", help="Tone: ironic, wholesome, unhinged, minimalist")
    parser.add_argument("--context", default="", help="Extra community context")
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    print(f"Generating merch ideas for: {args.topic}")
    result = ideate_merch(args.topic, vibe=args.vibe, community_context=args.context)

    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
