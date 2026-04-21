"""Research agent — the AI intern that investigates a topic and reports back.

Runs a 4-step pipeline:
  1. Universe Mapping — identify entities, moments, communities
  2. Evidence Gathering — mine Reddit/YouTube/web for each entity
  3. Insight Synthesis — draw conclusions from the evidence
  4. Sticker Opportunities — translate insights into merch concepts

Each step produces a Pydantic-validated JSON intermediate that can be
inspected, cached, and debugged independently.

Usage:
  python -m agents.research_agent "Bridgerton"
  python -m agents.research_agent "Owala water bottles" -o report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.builtin_tools import WebSearchTool
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from schemas.research import (
    CulturalInsight,
    EntityEvidence,
    ResearchReport,
    StickerOpportunity,
    UniverseMap,
)

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _build_model(model_name: str | None = None) -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(model_name or DEFAULT_MODEL, provider=provider)


def _retry(fn, retries=2):
    """Simple retry wrapper for LLM calls."""
    from utils.llm_retry import sync_retry_llm
    return sync_retry_llm(fn)


# ---------------------------------------------------------------------------
# Step 1: Universe Mapping
# ---------------------------------------------------------------------------

_universe_agent = Agent(
    model=_build_model(),
    system_prompt="""\
You map the cultural universe around ANY topic. This could be a TV show, a game,
a brand, an event, a subculture, a rivalry, a meme, a product, a place — anything.

Your job is to identify:
- The KEY ENTITIES: characters, people, products, teams, ships, factions
- The ICONIC MOMENTS: specific scenes, events, incidents, controversies, memes
- CULTURAL TOUCHPOINTS: crossovers with broader culture (brand tie-ins, viral audio, etc.)
- AESTHETIC ELEMENTS: visual signatures, colors, symbols, typography
- COMMUNITY HUBS: where people discuss this (subreddits, hashtags, creators)
- CURRENT CONTEXT: why is this in the conversation RIGHT NOW?

Use web search to find what's CURRENTLY happening, not just what you know from training.
Be specific — "the bath scene" not "romantic moments". Name names.
Aim for 8-15 entities, 5-10 moments, and 3-5 community hubs.\
""",
    output_type=UniverseMap,
    model_settings=GoogleModelSettings(temperature=0.3, max_tokens=4096),
    builtin_tools=[WebSearchTool()],
    retries=3,
)


def map_universe(topic: str) -> UniverseMap:
    """Step 1: Identify the cultural universe around a topic."""
    result = _retry(lambda: _universe_agent.run_sync(
        f"Map the cultural universe around: {topic}\n\n"
        "Use web search to find what's current. Be specific about entities, "
        "moments, and community hubs."
    ))
    return result.output


# ---------------------------------------------------------------------------
# Step 2: Evidence Gathering
# ---------------------------------------------------------------------------

_evidence_agent = Agent(
    model=_build_model(),
    system_prompt="""\
You are a research analyst gathering evidence about cultural entities/moments.
Given an entity or moment from a cultural universe, search for what people are
actually saying about it across Reddit, YouTube, TikTok, Twitter, and news.

For each entity, report:
- How much it's being discussed (mention volume)
- How people feel about it (sentiment)
- The NARRATIVE: what happened, why people care, how the conversation evolved
- 2-5 specific evidence sources with quotes

Write the narrative like a briefing for a marketing team — clear, concise,
opinionated. "Fans loved X but turned on Y when Z happened."

Use web search to find CURRENT discussions, not just general knowledge.\
""",
    output_type=EntityEvidence,
    model_settings=GoogleModelSettings(temperature=0.3, max_tokens=3072),
    builtin_tools=[WebSearchTool()],
    retries=3,
)


def gather_evidence(entity: str, topic: str) -> EntityEvidence:
    """Step 2: Gather evidence about a specific entity/moment."""
    result = _retry(lambda: _evidence_agent.run_sync(
        f"Research this entity/moment: \"{entity}\"\n"
        f"Context: this is part of the cultural universe of \"{topic}\"\n\n"
        "Search Reddit, YouTube, and the web for current discussions. "
        "What are people saying? How do they feel? What's the narrative?"
    ))
    return result.output


def gather_evidence_batch(
    entities: list[str], topic: str, max_entities: int = 8
) -> list[EntityEvidence]:
    """Gather evidence for multiple entities (sequential to avoid rate limits)."""
    results = []
    for entity in entities[:max_entities]:
        try:
            ev = gather_evidence(entity, topic)
            results.append(ev)
        except Exception as e:
            print(f"  Evidence gathering failed for '{entity}': {e}", file=sys.stderr)
            continue
    return results


# ---------------------------------------------------------------------------
# Step 3: Insight Synthesis
# ---------------------------------------------------------------------------

_insight_agent = Agent(
    model=_build_model(),
    system_prompt="""\
You synthesize cultural evidence into actionable insights for a sticker/merch
marketing team. You receive a universe map and evidence gathered about key
entities and moments.

Your job is to identify the CULTURAL MOMENTS that matter for merch:
- What's viral right now?
- What's controversial (controversy = merch opportunity)?
- What quotes/phrases are people repeating?
- What inside jokes would fans pay to put on their laptop?

For each insight:
- Name the moment specifically
- Explain what happened and how people reacted
- Rate the virality
- Suggest a sticker angle: what would the sticker say/show?
- Rate your confidence based on evidence volume

Aim for 5-10 insights, ranked by sticker potential. Quality over quantity.
Skip anything too generic to be a sticker ("this show is popular").\
""",
    output_type=list[CulturalInsight],
    model_settings=GoogleModelSettings(temperature=0.4, max_tokens=4096),
    retries=3,
)


def synthesize_insights(
    universe: UniverseMap, evidence: list[EntityEvidence]
) -> list[CulturalInsight]:
    """Step 3: Synthesize evidence into cultural insights."""
    context = json.dumps({
        "universe": universe.model_dump(),
        "evidence": [e.model_dump() for e in evidence],
    }, indent=2, ensure_ascii=False)

    result = _retry(lambda: _insight_agent.run_sync(
        f"Synthesize these research findings into cultural insights:\n\n{context}\n\n"
        "Identify the 5-10 most sticker-worthy cultural moments. "
        "Each insight should have a clear sticker angle."
    ))
    return result.output


# ---------------------------------------------------------------------------
# Step 4: Sticker Opportunities
# ---------------------------------------------------------------------------

_opportunity_agent = Agent(
    model=_build_model(),
    system_prompt="""\
You translate cultural insights into concrete, sellable sticker concepts.
You think like a merch designer who understands internet culture.

For each opportunity:
- A specific sticker concept (not vague — "Be My Mistress in Regency calligraphy")
- The exact text on the sticker (if text-based)
- A brief visual sketch
- Why it's timely (what cultural moment makes it relevant NOW)
- Who buys it (specific audience)
- The emotional hook (identity, humor, outrage, nostalgia, etc.)

Generate 8-12 opportunities spanning:
- 3-4 broad appeal (casual fans would get it)
- 4-5 fandom/community level (active participants)
- 2-3 deep cuts (die-hard fans only)

Be creative. Collide the topic's iconography with current internet language.
"Viscount Rizz" > "I like Bridgerton"\
""",
    output_type=list[StickerOpportunity],
    model_settings=GoogleModelSettings(temperature=0.8, max_tokens=4096),
    retries=3,
)


def generate_opportunities(
    universe: UniverseMap,
    insights: list[CulturalInsight],
) -> list[StickerOpportunity]:
    """Step 4: Generate sticker opportunities from cultural insights."""
    context = json.dumps({
        "universe": universe.model_dump(),
        "insights": [i.model_dump() for i in insights],
    }, indent=2, ensure_ascii=False)

    result = _retry(lambda: _opportunity_agent.run_sync(
        f"Generate sticker opportunities from this cultural intelligence:\n\n"
        f"{context}\n\n"
        "Create 8-12 concrete sticker concepts. Mix broad appeal, fandom-level, "
        "and deep cuts. Collide the topic's iconography with internet culture."
    ))
    return result.output


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

def run_research(
    topic: str,
    max_entities: int = 8,
    verbose: bool = True,
) -> ResearchReport:
    """Run the full 4-step research pipeline.

    Args:
        topic: Any cultural topic
        max_entities: Max entities to gather evidence for (controls cost/time)
        verbose: Print progress to stderr

    Returns:
        ResearchReport with universe, evidence, insights, and opportunities
    """
    if verbose:
        print(f"Step 1/4: Mapping the universe of '{topic}'...", file=sys.stderr)
    universe = map_universe(topic)
    if verbose:
        print(f"  Found {len(universe.entities)} entities, "
              f"{len(universe.iconic_moments)} moments", file=sys.stderr)

    # Pick the most interesting entities + moments to research
    research_targets = []
    # Prioritize iconic moments (more sticker-worthy than generic entities)
    research_targets.extend(universe.iconic_moments[:5])
    # Add key entities
    research_targets.extend(universe.entities[:5])
    # Add cultural touchpoints
    research_targets.extend(universe.cultural_touchpoints[:3])
    # Deduplicate
    seen = set()
    unique_targets = []
    for t in research_targets:
        key = t.lower().strip()
        if key not in seen:
            seen.add(key)
            unique_targets.append(t)

    if verbose:
        print(f"\nStep 2/4: Gathering evidence for {min(len(unique_targets), max_entities)} "
              f"entities/moments...", file=sys.stderr)
    evidence = gather_evidence_batch(unique_targets, topic, max_entities=max_entities)
    if verbose:
        print(f"  Gathered evidence for {len(evidence)} entities", file=sys.stderr)

    if verbose:
        print(f"\nStep 3/4: Synthesizing cultural insights...", file=sys.stderr)
    insights = synthesize_insights(universe, evidence)
    if verbose:
        print(f"  Generated {len(insights)} insights", file=sys.stderr)

    if verbose:
        print(f"\nStep 4/4: Generating sticker opportunities...", file=sys.stderr)
    opportunities = generate_opportunities(universe, insights)
    if verbose:
        print(f"  Generated {len(opportunities)} opportunities", file=sys.stderr)

    # Build executive summary
    hot = [i for i in insights if i.virality in ("viral", "trending")]
    summary = (
        f"Research on '{topic}' identified {len(universe.entities)} key entities, "
        f"{len(universe.iconic_moments)} iconic moments, and {len(evidence)} "
        f"evidence-backed narratives. "
        f"{len(hot)} moments are currently viral/trending. "
        f"Generated {len(opportunities)} sticker opportunities spanning "
        f"broad appeal to deep-cut fandom merch."
    )

    return ResearchReport(
        topic=topic,
        universe=universe,
        evidence=evidence,
        insights=insights,
        opportunities=opportunities,
        executive_summary=summary,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research a cultural topic and generate sticker opportunities"
    )
    parser.add_argument("topic", help="Any cultural topic")
    parser.add_argument("--max-entities", type=int, default=8)
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    report = run_research(args.topic, max_entities=args.max_entities)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"EXECUTIVE SUMMARY: {report.executive_summary}", file=sys.stderr)
    print(f"\nTOP INSIGHTS:", file=sys.stderr)
    for i in report.insights[:5]:
        print(f"  [{i.virality}] {i.moment}", file=sys.stderr)
        print(f"    → Sticker: {i.sticker_angle}", file=sys.stderr)
    print(f"\nTOP OPPORTUNITIES:", file=sys.stderr)
    for o in report.opportunities[:5]:
        print(f"  • {o.concept}", file=sys.stderr)
        print(f"    Why: {o.why_now}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    text = json.dumps(report.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"\nFull report: {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
