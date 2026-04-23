"""Generate sticker images using Gemini's Nano Banana image generation.

Takes a DesignSpec (image prompt) and produces a PNG sticker image.
Uses the google-genai SDK directly since PydanticAI doesn't wrap image generation.

Free tier: 500 images/day with gemini-2.5-flash.

Usage:
  python -m agents.image_gen_agent "kawaii cat holding a sign, transparent background, sticker design"
  python -m agents.image_gen_agent "retro 70s typography saying 'good vibes only'" -o stickers/good_vibes.png
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from utils.llm_retry import is_transient_gemini_error, sync_retry_llm

# Nano Banana image gen models available on this API key
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
IMAGE_MODEL_FALLBACK = os.getenv("GEMINI_IMAGE_MODEL_FALLBACK", "gemini-2.5-flash-image").strip()

# Default output directory
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "stickers"


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    return genai.Client(api_key=api_key)


def generate_sticker_image(
    prompt: str,
    *,
    output_path: Path | None = None,
    model: str = IMAGE_MODEL,
) -> Path:
    """Generate a sticker image from a text prompt.

    Args:
        prompt: The image generation prompt (from DesignSpec.image_prompt).
        output_path: Where to save the PNG. Auto-generated if None.
        model: Gemini model to use for image generation.

    Returns:
        Path to the saved PNG file.
    """
    client = _get_client()

    # Wrap the prompt with sticker-specific instructions
    full_prompt = (
        f"{prompt}\n\n"
        "Style requirements: clean die-cut sticker design, solid white or transparent background, "
        "no complex backgrounds, strong clean edges suitable for printing, high contrast."
    )

    def _call(m: str):
        return client.models.generate_content(
            model=m,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

    try:
        response = sync_retry_llm(lambda: _call(model))
    except Exception as e:
        if (
            IMAGE_MODEL_FALLBACK
            and IMAGE_MODEL_FALLBACK != model
            and is_transient_gemini_error(e)
        ):
            response = sync_retry_llm(lambda: _call(IMAGE_MODEL_FALLBACK))
        else:
            raise

    # Find the image part in the response
    image_saved = False
    text_response = ""

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        # Generate a filename from the first few words of the prompt
        slug = "_".join(prompt.split()[:5]).lower()
        slug = "".join(c for c in slug if c.isalnum() or c == "_")[:50]
        output_path = OUTPUT_DIR / f"{slug}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for part in response.parts:
        if part.text is not None:
            text_response = part.text
        elif part.inline_data is not None:
            image = part.as_image()
            image.save(str(output_path))
            image_saved = True

    if not image_saved:
        raise RuntimeError(
            f"No image was generated. Model response: {text_response or '(empty)'}"
        )

    return output_path


def generate_sticker_with_reference(
    prompt: str,
    reference_image_bytes: bytes,
    reference_mime: str = "image/png",
    *,
    output_path: Path | None = None,
    model: str = IMAGE_MODEL,
) -> Path:
    """Generate a sticker image using a reference/anchor image.

    Sends the reference image + text prompt to Gemini so it can use the
    image as visual context (style reference, character reference, etc.).

    Args:
        prompt: Text prompt describing what to generate.
        reference_image_bytes: Raw bytes of the reference image.
        reference_mime: MIME type of the reference image.
        output_path: Where to save the PNG.
        model: Gemini model to use.

    Returns:
        Path to the saved PNG file.
    """
    client = _get_client()

    full_prompt = (
        f"{prompt}\n\n"
        "Use the attached image as a reference/anchor for style, character, or composition. "
        "Generate a clean die-cut sticker design inspired by or incorporating elements from "
        "the reference. Solid white or transparent background, strong clean edges."
    )

    # Build multimodal content: text + image
    contents = [
        types.Part.from_text(text=full_prompt),
        types.Part.from_bytes(data=reference_image_bytes, mime_type=reference_mime),
    ]

    def _call(m: str):
        return client.models.generate_content(
            model=m,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

    try:
        response = sync_retry_llm(lambda: _call(model))
    except Exception as e:
        if IMAGE_MODEL_FALLBACK and IMAGE_MODEL_FALLBACK != model and is_transient_gemini_error(e):
            response = sync_retry_llm(lambda: _call(IMAGE_MODEL_FALLBACK))
        else:
            raise

    image_saved = False
    text_response = ""

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        slug = "_".join(prompt.split()[:5]).lower()
        slug = "".join(c for c in slug if c.isalnum() or c == "_")[:50]
        output_path = OUTPUT_DIR / f"ref_{slug}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for part in response.parts:
        if part.text is not None:
            text_response = part.text
        elif part.inline_data is not None:
            image = part.as_image()
            image.save(str(output_path))
            image_saved = True

    if not image_saved:
        raise RuntimeError(
            f"No image was generated. Model response: {text_response or '(empty)'}"
        )

    return output_path


def generate_from_design_spec(spec_json: dict, *, output_path: Path | None = None) -> Path:
    """Generate a sticker image from a DesignSpec dict.

    Args:
        spec_json: A DesignSpec as a dict (from .model_dump()).
        output_path: Where to save. Auto-generated if None.

    Returns:
        Path to the saved PNG.
    """
    prompt = spec_json.get("image_prompt", "")
    negative = spec_json.get("negative_prompt", "")

    if negative:
        prompt += f"\n\nAvoid: {negative}"

    return generate_sticker_image(prompt, output_path=output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate sticker images with Gemini Nano Banana"
    )
    parser.add_argument("prompt", help="Image generation prompt")
    parser.add_argument(
        "-o", "--out", type=Path, default=None,
        help="Output PNG path (default: outputs/stickers/<slug>.png)",
    )
    parser.add_argument(
        "--model", default=IMAGE_MODEL,
        help=f"Gemini model (default: {IMAGE_MODEL})",
    )
    args = parser.parse_args()

    print(f"Generating sticker image...")
    path = generate_sticker_image(args.prompt, output_path=args.out, model=args.model)
    print(f"Saved: {path}")


if __name__ == "__main__":
    main()
