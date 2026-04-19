"""Schemas for community text mining (Mode 3 — in-jokes & recurring phrases)."""

from typing import Literal

from pydantic import BaseModel, Field


class CommunityInsight(BaseModel):
    """AI interpretation of a recurring community phrase."""

    phrase: str = Field(description="The recurring phrase or in-joke")
    interpretation: str = Field(description="What this phrase means in context")
    why_its_sticky: str = Field(
        description="Why someone would put this on a laptop sticker"
    )
    sticker_potential: Literal["high", "medium", "low"] = Field(
        description="How well this translates to a sticker design"
    )
    suggested_style: str = Field(
        description="Art style that matches the vibe (e.g. 'retro pixel art', 'hand-lettered')"
    )
    target_audience: str = Field(
        description="Who would buy this sticker (e.g. 'Discord gamers', 'K-pop stans')"
    )


class CommunityAnalysis(BaseModel):
    """Output of the community analysis agent."""

    community_vibe: str = Field(
        description="Overall tone and culture of this community (1-2 sentences)"
    )
    insights: list[CommunityInsight] = Field(
        description="AI interpretations of recurring phrases, ordered by sticker potential"
    )
    recommended_sticker_pack: list[str] = Field(
        description="Top 3-5 phrases for a themed sticker pack"
    )
