"""Community configuration schema — lets users tune how AI agents discover content."""

from typing import Literal

from pydantic import BaseModel, Field


class CommunityConfig(BaseModel):
    """User-facing knobs for content discovery across different niches."""

    source_platforms: list[str] = Field(
        default=["reddit", "google_trends"],
        description="Which platforms to mine for trends (reddit, google_trends, tiktok, twitter, youtube)",
    )
    tone_filters: list[Literal["wholesome", "edgy", "ironic", "earnest"]] = Field(
        default=["wholesome", "ironic"],
        description="Desired tone of discovered content",
    )
    content_types: list[Literal["quotes", "visual_memes", "catchphrases", "lyrics"]] = Field(
        default=["quotes", "catchphrases"],
        description="What kinds of viral content to prioritize",
    )
    recency_window: Literal["24h", "week", "month", "evergreen"] = Field(
        default="week",
        description="How recent the trends should be",
    )
    target_subreddits: list[str] = Field(
        default_factory=list,
        description="Specific subreddits to mine (e.g. ['taylorswift', 'nba', 'kpop'])",
    )
