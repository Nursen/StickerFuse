"""Research agent schemas — domain-agnostic cultural intelligence pipeline.

Works for any topic: fandoms, brands, events, subcultures, rivalries,
memes, products, places, etc. No assumptions about the topic type.

Step 1: UniverseMap — what entities, communities, and touchpoints exist
Step 2: EntityEvidence — what people are saying about each entity
Step 3: CulturalInsight — synthesized conclusions about cultural moments
Step 4: StickerOpportunity — actionable merch concepts with evidence
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Step 1: Universe Mapping
# ---------------------------------------------------------------------------

class UniverseMap(BaseModel):
    """The cultural universe around a topic — entities, relationships, and
    community hubs. Domain-agnostic: works for shows, games, brands, events,
    subcultures, rivalries, memes, products, places, etc."""

    topic: str = Field(description="The input topic")
    topic_type: str = Field(
        description="What kind of cultural object this is: "
        "'fandom', 'brand', 'event', 'subculture', 'game', 'rivalry', "
        "'meme_format', 'product', 'place', 'person', 'movement', etc."
    )
    entities: list[str] = Field(
        description="Key named entities: characters, people, products, "
        "teams, factions, archetypes — whatever the building blocks are. "
        "Include ship names, pairings, rivalries if relevant."
    )
    iconic_moments: list[str] = Field(
        description="Specific scenes, events, incidents, drops, matches, "
        "controversies, memes — the moments people reference. Be specific: "
        "'the bath scene' not 'romantic moments'."
    )
    cultural_touchpoints: list[str] = Field(
        description="Crossovers with broader culture: brand tie-ins, "
        "viral audio, celebrity references, news coverage, parodies, "
        "TikTok trends, etc."
    )
    aesthetic_elements: list[str] = Field(
        description="Visual/stylistic signatures: color palettes, fashion, "
        "logos, symbols, typography styles, art movements associated with it"
    )
    community_hubs: list[str] = Field(
        description="Where fans/enthusiasts gather: subreddit names, "
        "hashtags, Discord servers, YouTube channels, TikTok creators, etc."
    )
    current_context: str = Field(
        description="What's happening RIGHT NOW: new season, recent event, "
        "controversy, product launch, anniversary, etc. Why is this topic "
        "in the cultural conversation today?"
    )


# ---------------------------------------------------------------------------
# Step 2: Evidence Gathering
# ---------------------------------------------------------------------------

class EvidenceSource(BaseModel):
    """A single piece of evidence from a platform."""
    platform: str = Field(description="reddit, youtube, tiktok, twitter, news, etc.")
    title: str = Field(description="Post/video/article title")
    url: str = Field(default="", description="Link if available")
    engagement: str = Field(
        description="Engagement metric: '2.3K upvotes', '1.2M views', etc."
    )
    quote: str = Field(
        default="",
        description="Key quote or comment that captures the sentiment"
    )


class EntityEvidence(BaseModel):
    """Evidence gathered about a specific entity or moment in the universe."""
    entity: str = Field(
        description="The entity or moment being researched: "
        "'Benedict + Sophie', 'the 360 dance', 'Owala Stanley rivalry', etc."
    )
    mention_volume: str = Field(
        description="Rough volume: 'heavily discussed', 'niche but passionate', "
        "'trending', 'fading', etc."
    )
    sentiment_summary: str = Field(
        description="How people feel: 'overwhelmingly positive', 'divisive', "
        "'ironic appreciation', 'outraged', 'nostalgic', etc."
    )
    narrative: str = Field(
        description="The STORY: what happened, why people care, how the "
        "conversation evolved. Write like a briefing for a marketing team."
    )
    sources: list[EvidenceSource] = Field(
        description="2-5 specific pieces of evidence backing this up"
    )


# ---------------------------------------------------------------------------
# Step 3: Cultural Insights
# ---------------------------------------------------------------------------

class CulturalInsight(BaseModel):
    """A synthesized conclusion about a cultural moment — the kind of thing
    a smart intern would report to the marketing team."""
    moment: str = Field(
        description="Short label: 'the mistress proposal backlash', "
        "'360 cello dance viral', 'Owala vs Stanley wars'"
    )
    what_happened: str = Field(
        description="1-2 sentence factual summary of the moment"
    )
    community_reaction: str = Field(
        description="How people responded: emotion, memes, takes, discourse"
    )
    virality: Literal["viral", "trending", "steady", "niche", "fading"] = Field(
        description="Current momentum level"
    )
    sticker_angle: str = Field(
        description="How this moment translates to merch: what would the "
        "sticker say/show? What's the joke or identity signal?"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="How confident are we in this insight? Based on evidence volume."
    )


# ---------------------------------------------------------------------------
# Step 4: Sticker Opportunities
# ---------------------------------------------------------------------------

class StickerOpportunity(BaseModel):
    """An actionable sticker concept backed by cultural research."""
    concept: str = Field(
        description="The sticker concept in one line: "
        "'Be My Mistress in Regency calligraphy'"
    )
    text_on_sticker: str | None = Field(
        default=None,
        description="Exact text on the sticker (None if image-only)"
    )
    visual_sketch: str = Field(
        description="Brief visual description for the designer"
    )
    why_now: str = Field(
        description="Why this is timely: what cultural moment makes it relevant"
    )
    target_buyer: str = Field(
        description="Who buys this: 'Bridgerton fans who love Benedict', "
        "'water bottle collectors', 'ironic meme enjoyers'"
    )
    estimated_appeal: Literal["broad", "fandom", "deep_cut"] = Field(
        description="Who gets it: 'broad' = casual fans + internet users, "
        "'fandom' = active fans, 'deep_cut' = die-hard / subreddit regulars"
    )
    emotional_hook: str = Field(
        description="What emotion drives the purchase: 'insider identity', "
        "'ironic humor', 'nostalgia', 'outrage merch', 'wholesome fandom'"
    )
    source_insight: str = Field(
        description="Which cultural insight this came from"
    )


# ---------------------------------------------------------------------------
# Full Research Report
# ---------------------------------------------------------------------------

class ResearchReport(BaseModel):
    """Complete output of the research agent — the full intelligence brief."""
    topic: str
    universe: UniverseMap
    evidence: list[EntityEvidence] = Field(
        description="Evidence gathered for key entities/moments"
    )
    insights: list[CulturalInsight] = Field(
        description="Synthesized cultural insights, ranked by virality"
    )
    opportunities: list[StickerOpportunity] = Field(
        description="Sticker concepts backed by research"
    )
    executive_summary: str = Field(
        description="3-5 sentence briefing for the marketing team: "
        "what's the cultural landscape, what's hot, what's the play?"
    )
