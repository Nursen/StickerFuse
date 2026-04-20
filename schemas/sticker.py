"""Schemas for sticker idea generation (Stage 4 of the pipeline)."""

from typing import Literal

from pydantic import BaseModel, Field


class StickerIdea(BaseModel):
    """A concrete sticker concept with visual direction."""

    concept_description: str = Field(
        description="One-line description of the sticker concept"
    )
    text_content: str | None = Field(
        default=None,
        description="Text that appears on the sticker (None for image-only stickers)",
    )
    visual_description: str = Field(
        description="What the sticker image looks like — described for an image generation model"
    )
    art_style: Literal[
        "kawaii", "retro", "minimalist", "hand-lettered",
        "pop-art", "grunge", "watercolor", "pixel-art",
    ] = Field(description="The visual art style for the sticker")
    layout_type: Literal["text_only", "image_only", "text_and_image"] = Field(
        description="Whether the sticker is text, image, or both"
    )
    color_palette: list[str] = Field(
        description="Suggested colors (e.g. ['pastel pink', 'white', 'gold'])"
    )
    viral_bite_ref: str = Field(
        description="The viral bite text this sticker is based on"
    )


class StickerIdeaSet(BaseModel):
    """Output of the sticker idea generation agent."""

    viral_bite: str = Field(description="The viral bite these sticker ideas are based on")
    ideas: list[StickerIdea] = Field(description="Generated sticker concepts (typically 3-5 per bite)")


class PhraseOptionSet(BaseModel):
    """Distinct phrase options before styling (Studio phrase-focused step)."""

    phrases: list[str] = Field(
        description="Exactly 5 distinct short sticker phrases (different wordings, same cultural moment)"
    )
