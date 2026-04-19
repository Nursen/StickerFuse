"""Schemas for topic input and subtopic discovery (Stages 1-2 of the pipeline)."""

from typing import Literal

from pydantic import BaseModel, Field


class TopicInput(BaseModel):
    """User-provided topic to explore."""

    topic: str = Field(description="The cultural topic to explore (e.g. 'Taylor Swift', 'NBA playoffs', 'cottagecore')")
    context: str = Field(default="", description="Optional extra context about what angle the user cares about")


class Subtopic(BaseModel):
    """A timely subtopic discovered from social media signals."""

    name: str = Field(description="Short name of the subtopic (e.g. 'Travis Kelce engagement')")
    description: str = Field(description="Why this subtopic is relevant and trending right now")
    trending_score: Literal["hot", "warm", "steady"] = Field(
        description="How actively trending this subtopic is"
    )
    source_platform: str = Field(
        description="Where the trend signal came from (reddit, google_trends, tiktok, etc.)"
    )
    recency: str = Field(
        description="How recent the trend is (e.g. 'last 24h', 'this week', 'ongoing')"
    )
    sample_signals: list[str] = Field(
        default_factory=list,
        description="Example posts, search queries, or data points that evidence the trend",
    )
    # Optional hard metrics from TrendSignal (populated when trend_scorer data is available)
    spike_score: float | None = Field(
        default=None, description="How far above baseline (from trend_scorer)"
    )
    engagement_velocity: float | None = Field(
        default=None, description="Engagement per hour (from trend_scorer)"
    )
    post_count: int | None = Field(
        default=None, description="Number of posts backing this trend"
    )
    evidence_urls: list[str] = Field(
        default_factory=list,
        description="URLs to actual posts/pages backing this trend",
    )


class SubtopicResult(BaseModel):
    """Output of the subtopic discovery agent."""

    topic: str = Field(description="The parent topic that was explored")
    subtopics: list[Subtopic] = Field(description="Discovered subtopics, ordered by trending_score")
