"""Schemas for data-backed trend detection — every trend has verifiable metrics."""

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A single piece of evidence supporting a trend."""

    source: str = Field(description="Platform source: 'reddit', 'google_trends'")
    url: str = Field(description="Link to the actual post/page")
    title: str = Field(description="Title of the post or query text")
    metric_name: str = Field(
        description="What's being measured: 'score', 'upvote_ratio', 'search_interest', 'num_comments'"
    )
    metric_value: float = Field(description="The numeric value of the metric")
    timestamp: str = Field(description="ISO datetime of when this evidence was recorded")


class TrendSignal(BaseModel):
    """A quantified, verifiable trend signal with hard metrics."""

    name: str = Field(description="What the trend is about")
    description: str = Field(description="Brief human description")

    # Hard metrics
    post_count: int = Field(description="How many posts about this")
    total_engagement: int = Field(description="Sum of scores/upvotes across posts")
    avg_engagement_rate: float = Field(description="Average score per post")
    engagement_velocity: float = Field(
        description="Engagement per hour (higher = faster growing)"
    )
    spike_score: float = Field(
        description="How far above baseline (1.0 = normal, 2.0 = 2x normal)"
    )
    peak_post_score: int = Field(description="Highest individual post score")
    comment_volume: int = Field(description="Total comments across posts")

    # Time context
    time_window: str = Field(description="e.g. 'last 24h', 'last 7d'")
    first_seen: str = Field(description="ISO datetime of earliest post")
    peak_time: str = Field(description="ISO datetime of highest engagement")
    trend_direction: Literal["rising", "peaking", "falling", "steady"] = Field(
        description="Which way the trend is moving"
    )

    # Google Trends correlation (if available)
    search_interest: int | None = Field(
        default=None, description="Google Trends score (0-100)"
    )
    search_interest_change: str | None = Field(
        default=None, description="e.g. '+250%' or 'Breakout'"
    )

    # Cross-platform correlation
    platform_count: int = Field(
        default=1, description="How many platforms confirm this trend"
    )
    cross_platform_score: float = Field(
        default=0.0, description="Weighted cross-platform strength"
    )
    platforms_confirmed: list[str] = Field(
        default_factory=list, description="Which platforms have signals"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="low", description="Based on cross-platform + spike"
    )
    wikipedia_spike_ratio: float | None = Field(
        default=None, description="Wikipedia pageview spike ratio vs baseline"
    )
    youtube_view_velocity: float | None = Field(
        default=None, description="YouTube views per hour for top video"
    )
    web_mentions: int | None = Field(
        default=None, description="Number of web search results mentioning this"
    )

    # Sentiment analysis
    sentiment_score: float | None = Field(
        default=None, description="Avg VADER compound score (-1 to +1)"
    )
    emotional_intensity: float | None = Field(
        default=None, description="Fraction of posts with |compound| > 0.5"
    )
    sentiment_label: str | None = Field(
        default=None,
        description="Overall sentiment: strong_positive, positive, neutral, negative, strong_negative",
    )

    # Poisson spike detection
    poisson_eta: float | None = Field(
        default=None, description="Statistical spike score (eta) from Poisson model"
    )
    spike_magnitude: str | None = Field(
        default=None, description="none, mild, notable, or extreme"
    )

    # Velocity forecast
    velocity_slope: float | None = Field(
        default=None, description="Engagement per hour (positive = growing)"
    )
    velocity_r_squared: float | None = Field(
        default=None, description="Prediction confidence (0-1, higher = more confident)"
    )
    trajectory: str | None = Field(
        default=None,
        description="Trend trajectory: accelerating, stable, decelerating, fading, volatile",
    )
    predicted_72h: float | None = Field(
        default=None, description="Predicted engagement level in 72 hours"
    )
    will_be_trending_in_3_days: bool | None = Field(
        default=None, description="Whether the trend is predicted to still be active in 3 days"
    )

    # Evidence
    evidence: list[EvidenceItem] = Field(
        description="Actual posts/data backing this up"
    )
    source_platforms: list[str] = Field(
        description="Which platforms this was detected on"
    )


class TrendReport(BaseModel):
    """Output of the trend analysis — a ranked list of verified trends."""

    query: str = Field(description="What was searched for")
    analyzed_at: str = Field(description="ISO datetime")
    total_posts_analyzed: int
    total_subreddits_scanned: int
    trends: list[TrendSignal] = Field(
        description="Ordered by spike_score descending"
    )
