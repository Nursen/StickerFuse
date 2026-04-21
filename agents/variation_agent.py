"""Generates 3 deliberately distinct visual directions for a sticker concept.

Instead of running the same prompt 3 times (which gives near-identical results),
this agent creates 3 genuinely different creative interpretations of the same idea —
varying the visual approach, composition, character, emphasis, and mood.

Uses Gemini Flash-Lite (cheap) since this is prompt writing, not image generation.

Usage:
  python -m agents.variation_agent "Viscount Rizz" --style kawaii --context "Bridgerton"
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

DEFAULT_MODEL = os.getenv("GEMINI_MODEL_LITE", "gemini-2.5-flash-lite")


class StickerVariation(BaseModel):
    """A single distinct visual direction for a sticker."""
    variation_label: str = Field(description="Short label: 'Character-focused', 'Typography-led', 'Visual pun', etc.")
    image_prompt: str = Field(description="Complete, detailed image generation prompt for this variation")
    what_makes_it_different: str = Field(description="One sentence on why this variation is distinct from the others")


class VariationSet(BaseModel):
    """3 deliberately distinct variations of the same sticker concept."""
    concept: str = Field(description="The original sticker concept")
    variations: list[StickerVariation] = Field(description="Exactly 3 distinct visual directions")


SYSTEM_PROMPT = """\
You create 3 DELIBERATELY DISTINCT visual directions for a sticker design. Each variation \
must be a genuinely different creative interpretation — not the same image with minor tweaks.

Ways to create real variation:
- **Composition**: one is character-focused, one is typography-led, one is an icon/symbol
- **Approach**: one is literal, one is metaphorical, one is a visual pun
- **Subject**: one features a character, one features an object/prop, one is abstract
- **Mood**: one is cute/wholesome, one is dramatic, one is ironic/funny
- **Scale**: one is a full scene, one is a close-up detail, one is a pattern

For each variation, write a COMPLETE image generation prompt that would produce a distinct \
sticker. Include: subject, pose/composition, style details, colors, background treatment, \
and any text placement. The prompt must work standalone — don't reference the other variations.

CRITICAL RULES:
- All 3 must be die-cut sticker designs (clean edges, simple background)
- All 3 must reference the same cultural idea/joke
- All 3 must work at 3-inch sticker size (readable, clear silhouette)
- Each prompt should be 2-4 sentences, specific and detailed
- If text appears on the sticker, specify the exact text and font style\
"""


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(DEFAULT_MODEL, provider=provider)


variation_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=VariationSet,
    model_settings=GoogleModelSettings(temperature=0.9, max_tokens=2048),
    retries=3,
)


def generate_variations(
    sticker_text: str,
    art_style: str = "",
    layout: str = "",
    visual_direction: str = "",
    color_mood: str = "",
    context: str = "",
) -> VariationSet:
    """Generate 3 distinct visual directions for a sticker concept.

    Args:
        sticker_text: The text/concept for the sticker
        art_style: Chosen art style (kawaii, retro, etc.)
        layout: text_only, image_only, or text_and_image
        visual_direction: User's visual description
        color_mood: Color palette preference
        context: Fandom/cultural context
    """
    parts = [f'Sticker concept: "{sticker_text}"']

    if art_style:
        parts.append(f"Art style: {art_style}")
    if layout:
        parts.append(f"Layout: {layout}")
    if visual_direction:
        parts.append(f"Visual direction from user: {visual_direction}")
    if color_mood:
        parts.append(f"Color mood: {color_mood}")
    if context:
        parts.append(f"Cultural context: {context}")

    parts.append(
        "Create exactly 3 DISTINCT visual directions for this sticker. "
        "Each must be a genuinely different creative approach, not minor tweaks."
    )

    from utils.llm_retry import sync_retry_llm
    result = sync_retry_llm(lambda: variation_agent.run_sync("\n\n".join(parts)))
    return result.output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate 3 distinct sticker variations")
    parser.add_argument("concept", help="Sticker text/concept")
    parser.add_argument("--style", default="", help="Art style")
    parser.add_argument("--layout", default="", help="Layout type")
    parser.add_argument("--visual", default="", help="Visual direction")
    parser.add_argument("--colors", default="", help="Color mood")
    parser.add_argument("--context", default="", help="Cultural context")
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    print(f"Generating 3 variations for: {args.concept}")
    result = generate_variations(
        args.concept, art_style=args.style, layout=args.layout,
        visual_direction=args.visual, color_mood=args.colors, context=args.context,
    )

    for i, v in enumerate(result.variations):
        print(f"\n  Variation {i+1} [{v.variation_label}]:")
        print(f"    {v.image_prompt}")
        print(f"    Why different: {v.what_makes_it_different}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result.model_dump(), indent=2), encoding="utf-8")
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
