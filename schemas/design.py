"""Schemas for design generation (Stage 5 of the pipeline)."""

from typing import Literal

from pydantic import BaseModel, Field


class DesignSpec(BaseModel):
    """Specification for generating a print-ready sticker design."""

    image_prompt: str = Field(
        description="The full prompt to send to the image generation model (DALL-E / Flux)"
    )
    negative_prompt: str = Field(
        default="",
        description="What to avoid in the generated image",
    )
    dimensions: str = Field(
        default="3x3 inch",
        description="Physical dimensions of the sticker",
    )
    background: Literal["transparent", "solid"] = Field(
        default="transparent",
        description="Background type — transparent for Cricut-ready die-cut stickers",
    )
    export_formats: list[str] = Field(
        default=["PNG"],
        description="Output file formats",
    )
    sticker_idea_ref: str = Field(
        description="The sticker idea concept this design is based on",
    )
