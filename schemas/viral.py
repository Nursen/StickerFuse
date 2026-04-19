"""Schemas for viral bite discovery (Stage 3 of the pipeline)."""

from typing import Literal

from pydantic import BaseModel, Field


class ViralBite(BaseModel):
    """A hyper-niche, monetizable viral moment — a quote, phrase, or meme concept."""

    text: str = Field(description="The catchphrase, quote, lyric, or meme text itself")
    context: str = Field(description="Why this is viral — the cultural moment behind it")
    source_type: Literal["quote", "lyric", "meme_text", "catchphrase", "hashtag"] = Field(
        description="What kind of viral content this is"
    )
    virality_signals: list[str] = Field(
        description="Evidence of virality (e.g. 'top post on r/taylorswift', '2M TikTok views', 'Google Trends spike')"
    )
    monetization_potential: Literal["high", "medium", "low"] = Field(
        description="How well this translates to a sellable sticker design"
    )
    subtopic_ref: str = Field(description="Which subtopic this viral bite belongs to")


class ViralBiteCollection(BaseModel):
    """Output of the viral bite discovery agent."""

    subtopic: str = Field(description="The subtopic these viral bites were discovered from")
    bites: list[ViralBite] = Field(description="Discovered viral bites, ordered by monetization_potential")
