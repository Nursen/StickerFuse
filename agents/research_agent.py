"""Research agent — the AI intern that investigates a topic and reports back.

Runs a 4-step pipeline:
  1. Universe Mapping — identify entities, moments, communities (Flash + web search)
  2. Evidence Gathering — mine Reddit/YouTube/web for each entity (Flash + web search, parallel)
  3. Insight Synthesis — draw conclusions from evidence (Flash — needs reasoning)
  4. Sticker Opportunities — translate insights into merch (Flash-Lite — creative text, cheap)

Cost-optimized: uses Flash-Lite where reasoning isn't needed, parallelizes
evidence gathering, feeds in data from our existing miners to reduce web
search calls.

Usage:
  python -m agents.research_agent "Bridgerton"
  python -m agents.research_agent "Owala water bottles" -o report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Model tiers — use the cheapest model that can do the job
_FLASH = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_FLASH_LITE = os.getenv("GEMINI_MODEL_LITE", "gemini-2.5-flash-lite")

# Lazy-built agents (avoid import-time API key check)
_agents: dict[str, Agent] = {}


def _get_provider() -> GoogleProvider:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    return GoogleProvider(api_key=api_key)


def _get_agent(name: str) -> Agent:
    if name in _agents:
        return _agents[name]

    provider = _get_provider()

    if name == "universe":
        agent = Agent(
            model=GoogleModel(_FLASH, provider=provider),
            system_prompt=_UNIVERSE_PROMPT,
            output_type=UniverseMap,
            model_settings=GoogleModelSettings(temperature=0.3, max_tokens=4096),
            builtin_tools=[WebSearchTool()],
            retries=3,
        )
    elif name == "evidence":
        agent = Agent(
            model=GoogleModel(_FLASH, provider=provider),
            system_prompt=_EVIDENCE_PROMPT,
            output_type=EntityEvidence,
            model_settings=GoogleModelSettings(temperature=0.3, max_tokens=3072),
            builtin_tools=[WebSearchTool()],
            retries=3,
        )
    elif name == "insights":
        agent = Agent(
            model=GoogleModel(_FLASH, provider=provider),
            system_prompt=_INSIGHTS_PROMPT,
            output_type=list[CulturalInsight],
            model_settings=GoogleModelSettings(temperature=0.4, max_tokens=4096),
            retries=3,
        )
    elif name == "opportunities":
        # Creative text gen — Flash-Lite is 5x cheaper and good enough
        agent = Agent(
            model=GoogleModel(_FLASH_LITE, provider=provider),
            system_prompt=_OPPORTUNITIES_PROMPT,
            output_type=list[StickerOpportunity],
            model_settings=GoogleModelSettings(temperature=0.8, max_tokens=4096),
            retries=3,
        )
    else:
        raise ValueError(f"Unknown agent: {name}")

    _agents[name] = agent
    return agent


def _retry(fn):
    from utils.llm_retry import sync_retry_llm
    return sync_retry_llm(fn)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_UNIVERSE_PROMPT = """\
You map the cultural universe around ANY topic — TV shows, games, brands, events,
subcultures, rivalries, memes, products, places, people, movements.

Identify:
- KEY ENTITIES: characters, people, products, teams, ships, factions (8-15)
- ICONIC MOMENTS: specific scenes, events, incidents, controversies, memes (5-10)
- CULTURAL TOUCHPOINTS: crossovers with broader culture (brand tie-ins, viral audio, etc.)
- AESTHETIC ELEMENTS: visual signatures, colors, symbols, typography
- COMMUNITY HUBS: where people discuss this (subreddits, hashtags, creators)
- CURRENT CONTEXT: what's happening RIGHT NOW — why is this in the conversation today?

Use web search to find what's CURRENT. Be specific — "the bath scene" not "romantic moments".\
"""

_EVIDENCE_PROMPT = """\
You gather evidence about cultural entities/moments. Search Reddit, YouTube, TikTok,
Twitter, and news for what people are CURRENTLY saying.

Report:
- Mention volume: 'heavily discussed', 'niche but passionate', 'trending', 'fading'
- Sentiment: 'overwhelmingly positive', 'divisive', 'ironic appreciation', etc.
- NARRATIVE: what happened, why people care, how the conversation evolved
- 2-5 specific evidence sources with quotes

Write like a briefing for a marketing team. Use web search for CURRENT discussions.\
"""

_INSIGHTS_PROMPT = """\
Synthesize cultural evidence into actionable insights for a sticker/merch team.

Identify the CULTURAL MOMENTS that matter for merch:
- What's viral? What's controversial? What quotes are people repeating?
- What inside jokes would fans put on their laptop?

For each insight: name the moment, explain what happened, rate virality,
suggest a sticker angle, rate confidence. Aim for 5-10 insights ranked by
sticker potential. Skip anything too generic.\
"""

_OPPORTUNITIES_PROMPT = """\
You are a merch designer creating a DIVERSE sticker collection. You need a healthy \
mix of straightforward fan favorites AND clever internet culture mashups.

Generate 12-15 concepts across these tiers:

BROAD APPEAL (4-5 stickers) — simple, pretty, immediately recognizable:
- Ship names in beautiful typography ("Kanthony" in elegant script)
- Character names or titles as identity statements ("Team Benedict")
- Iconic quotes in their original form ("I burn for you")
- Clean aesthetic pieces (the Bridgerton bee, a recognizable symbol)
- These are the BESTSELLERS. Simple, pretty, identity-signaling.

CLEVER MASHUPS (4-5 stickers) — fandom × internet culture collisions:
- Character traits × Gen Z slang ("Viscount Rizz", "Let Benedict Cook")
- Iconic moments × meme formats ("Be My Mistress" as reclaimed humor)
- Fandom in-jokes × trending phrases ("No Icks, Just Bees")
- These make fans laugh and share. The punchline sells it.

DEEP CUTS (3-4 stickers) — for the hardcore fans:
- Niche references only subreddit regulars would get
- Specific scene callbacks, obscure character moments
- Community in-jokes that signal "I'm one of you"

Rules:
- Text should be SHORT (1-6 words ideal)
- Not everything needs to be a pun. "Kanthony" in pretty script IS a sticker.
- Not everything needs internet slang. "I burn for you" IS a sticker.
- Mix text-only, image-only, and text+image across the set
- The collection should feel cohesive as a pack, not random

For each: specific concept, exact sticker text, visual sketch, why NOW, \
who buys it, emotional hook, and estimated appeal level.\
"""


# ---------------------------------------------------------------------------
# Step 1: Universe Mapping
# ---------------------------------------------------------------------------

def map_universe(topic: str) -> UniverseMap:
    agent = _get_agent("universe")
    result = _retry(lambda: agent.run_sync(
        f"Map the cultural universe around: {topic}\n\n"
        "Use web search to find what's current. Be specific."
    ))
    return result.output


# ---------------------------------------------------------------------------
# Step 2: Evidence Gathering (parallelized)
# ---------------------------------------------------------------------------

def gather_evidence(entity: str, topic: str) -> EntityEvidence:
    agent = _get_agent("evidence")
    result = _retry(lambda: agent.run_sync(
        f"Research: \"{entity}\" (part of the cultural universe of \"{topic}\")\n\n"
        "Search for current discussions. What are people saying? How do they feel?"
    ))
    return result.output


def _gather_one(entity: str, topic: str) -> EntityEvidence | None:
    """Wrapper for thread pool — returns None on failure."""
    try:
        return gather_evidence(entity, topic)
    except Exception as e:
        print(f"  ⚠ Evidence failed for '{entity}': {e}", file=sys.stderr)
        return None


def gather_evidence_parallel(
    entities: list[str], topic: str, max_entities: int = 8, max_workers: int = 3
) -> list[EntityEvidence]:
    """Gather evidence in parallel (3 concurrent web search calls)."""
    targets = entities[:max_entities]
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_gather_one, e, topic): e for e in targets}
        for future in as_completed(futures):
            entity = futures[future]
            ev = future.result()
            if ev:
                results.append(ev)
                print(f"  ✓ {entity}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# Step 3: Insight Synthesis
# ---------------------------------------------------------------------------

def synthesize_insights(
    universe: UniverseMap,
    evidence: list[EntityEvidence],
    miner_context: str = "",
) -> list[CulturalInsight]:
    """Synthesize evidence into cultural insights.

    Args:
        universe: The universe map
        evidence: Gathered evidence
        miner_context: Optional extra context from Reddit/YouTube miners
    """
    agent = _get_agent("insights")
    context = json.dumps({
        "universe": universe.model_dump(),
        "evidence": [e.model_dump() for e in evidence],
    }, indent=2, ensure_ascii=False)

    extra = f"\n\nAdditional data from community mining:\n{miner_context}" if miner_context else ""

    result = _retry(lambda: agent.run_sync(
        f"Synthesize into cultural insights:\n\n{context}{extra}\n\n"
        "Identify the 5-10 most sticker-worthy cultural moments."
    ))
    return result.output


# ---------------------------------------------------------------------------
# Step 4: Sticker Opportunities (Flash-Lite — cheap)
# ---------------------------------------------------------------------------

def generate_opportunities(
    universe: UniverseMap,
    insights: list[CulturalInsight],
) -> list[StickerOpportunity]:
    agent = _get_agent("opportunities")
    context = json.dumps({
        "universe": universe.model_dump(),
        "insights": [i.model_dump() for i in insights],
    }, indent=2, ensure_ascii=False)

    result = _retry(lambda: agent.run_sync(
        f"Generate sticker opportunities:\n\n{context}\n\n"
        "Create 8-12 concepts. Mix broad, fandom, and deep cuts."
    ))
    return result.output


# ---------------------------------------------------------------------------
# Optional: feed in our existing miners for richer evidence
# ---------------------------------------------------------------------------

def _mine_supplementary(topic: str) -> str:
    """Run Reddit + YouTube miners for extra context. Best-effort."""
    parts = []
    try:
        from miners.reddit_miner import mine_multiple_subreddits
        subreddit = topic.lower().replace(" ", "")
        reddit = mine_multiple_subreddits(
            [subreddit], limit=10, include_comments=True, max_comment_posts=5
        )
        for sub in reddit.get("subreddits", []):
            for post in sub.get("posts", [])[:5]:
                parts.append(f"[Reddit {post.get('score', 0)}↑] {post.get('title', '')}")
                for c in post.get("top_comments", [])[:3]:
                    parts.append(f"  [{c.get('score', 0)}↑] {c.get('body', '')[:120]}")
    except Exception:
        pass

    try:
        from miners.youtube_miner import mine_youtube
        yt = mine_youtube(topic, limit=8)
        for v in yt.get("videos", [])[:5]:
            views = v.get("view_count", 0)
            parts.append(f"[YouTube {views} views] {v.get('title', '')}")
    except Exception:
        pass

    return "\n".join(parts[:40])  # cap at 40 lines


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

def run_research(
    topic: str,
    max_entities: int = 6,
    use_miners: bool = True,
    verbose: bool = True,
) -> ResearchReport:
    """Run the full 4-step research pipeline.

    Args:
        topic: Any cultural topic
        max_entities: Max entities to gather evidence for
        use_miners: Also run Reddit/YouTube miners for supplementary data
        verbose: Print progress to stderr
    """
    if verbose:
        print(f"Step 1/4: Mapping the universe of '{topic}'...", file=sys.stderr)
    universe = map_universe(topic)
    if verbose:
        print(f"  {len(universe.entities)} entities, "
              f"{len(universe.iconic_moments)} moments, "
              f"{len(universe.community_hubs)} communities", file=sys.stderr)

    # Pick research targets — moments first (more sticker-worthy), then entities
    targets = []
    seen = set()
    for item in (universe.iconic_moments + universe.entities + universe.cultural_touchpoints):
        key = item.lower().strip()
        if key not in seen:
            seen.add(key)
            targets.append(item)

    # Mine supplementary data in parallel with evidence gathering
    miner_context = ""
    if use_miners:
        if verbose:
            print(f"\nMining Reddit + YouTube for supplementary data...", file=sys.stderr)
        try:
            miner_context = _mine_supplementary(topic)
            if verbose and miner_context:
                lines = miner_context.count("\n") + 1
                print(f"  {lines} supplementary data points", file=sys.stderr)
        except Exception:
            pass

    if verbose:
        n = min(len(targets), max_entities)
        print(f"\nStep 2/4: Gathering evidence for {n} entities (parallel)...", file=sys.stderr)
    evidence = gather_evidence_parallel(targets, topic, max_entities=max_entities)
    if verbose:
        print(f"  {len(evidence)} entities researched", file=sys.stderr)

    if verbose:
        print(f"\nStep 3/4: Synthesizing cultural insights...", file=sys.stderr)
    insights = synthesize_insights(universe, evidence, miner_context=miner_context)
    if verbose:
        print(f"  {len(insights)} insights", file=sys.stderr)

    if verbose:
        print(f"\nStep 4/4: Generating sticker opportunities (Flash-Lite)...", file=sys.stderr)
    opportunities = generate_opportunities(universe, insights)
    if verbose:
        print(f"  {len(opportunities)} opportunities", file=sys.stderr)

    hot = [i for i in insights if i.virality in ("viral", "trending")]
    summary = (
        f"Research on '{topic}': {len(universe.entities)} entities, "
        f"{len(universe.iconic_moments)} moments, {len(evidence)} researched. "
        f"{len(hot)} currently viral/trending. "
        f"{len(opportunities)} sticker opportunities generated."
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
    parser.add_argument("--max-entities", type=int, default=6)
    parser.add_argument("--no-miners", action="store_true", help="Skip Reddit/YouTube mining")
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    report = run_research(
        args.topic, max_entities=args.max_entities, use_miners=not args.no_miners
    )

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"SUMMARY: {report.executive_summary}", file=sys.stderr)
    print(f"\nINSIGHTS:", file=sys.stderr)
    for i in report.insights[:5]:
        print(f"  [{i.virality}] {i.moment}", file=sys.stderr)
        print(f"    → {i.sticker_angle}", file=sys.stderr)
    print(f"\nOPPORTUNITIES:", file=sys.stderr)
    for o in report.opportunities[:5]:
        print(f"  • {o.concept}", file=sys.stderr)
        print(f"    {o.why_now}", file=sys.stderr)
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
