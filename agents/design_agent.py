"""Agent that converts a sticker idea into an image generation prompt (DesignSpec).

Usage:
  python -m agents.design_agent "kawaii cat holding a sign that says 'I'm the problem'"
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

from schemas.design import DesignSpec

load_dotenv()
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """\
You are an expert at writing prompts for AI image generation models (DALL-E, Flux, Midjourney).
Your specialty is creating prompts that produce clean, print-ready sticker designs.

Given a sticker idea (concept, visual description, art style, colors), craft the perfect
image generation prompt. The output must work as a die-cut sticker:

- Transparent or solid white background
- Clean edges and strong silhouette
- No complex backgrounds or scenes
- Text must be clearly readable if included
- Style-appropriate (kawaii = cute rounded shapes, retro = halftone dots, etc.)

Also include a negative prompt to avoid common issues:
- No watermarks, signatures, or borders
- No photorealistic human faces (uncanny valley on stickers)
- No busy backgrounds

The image_prompt should be detailed enough for a single API call to produce a usable result.\
"""


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(DEFAULT_MODEL, provider=provider)


design_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=DesignSpec,
)


def generate_design_spec(
    concept: str,
    art_style: str = "",
    colors: str = "",
) -> DesignSpec:
    """Generate an image generation prompt from a sticker concept."""
    parts = [f"Sticker concept: {concept}"]
    if art_style:
        parts.append(f"Art style: {art_style}")
    if colors:
        parts.append(f"Color palette: {colors}")
    parts.append(
        "Create a detailed image generation prompt for this sticker design. "
        "It must be Cricut-compatible (clean edges, transparent background)."
    )

    result = design_agent.run_sync("\n\n".join(parts))
    return result.output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a design spec from a sticker concept")
    parser.add_argument("concept", help="Sticker concept description")
    parser.add_argument("--style", default="", help="Art style")
    parser.add_argument("--colors", default="", help="Color palette")
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    print(f"Generating design spec for: {args.concept}")
    result = generate_design_spec(args.concept, art_style=args.style, colors=args.colors)

    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
