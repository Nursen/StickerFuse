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
    elif name == "opps_favorites":
        agent = Agent(
            model=GoogleModel(_FLASH, provider=provider),
            system_prompt=_FAVORITES_PROMPT,
            output_type=list[StickerOpportunity],
            model_settings=GoogleModelSettings(temperature=0.5, max_tokens=3072),
            retries=3,
        )
    elif name == "opps_mashups":
        # Mashups need web search to find CURRENT internet slang — worth the cost
        agent = Agent(
            model=GoogleModel(_FLASH, provider=provider),
            system_prompt=_MASHUPS_PROMPT,
            output_type=list[StickerOpportunity],
            model_settings=GoogleModelSettings(temperature=0.9, max_tokens=3072),
            builtin_tools=[WebSearchTool()],
            retries=3,
        )
    elif name == "opps_deep":
        agent = Agent(
            model=GoogleModel(_FLASH, provider=provider),
            system_prompt=_DEEP_CUTS_PROMPT,
            output_type=list[StickerOpportunity],
            model_settings=GoogleModelSettings(temperature=0.7, max_tokens=3072),
            retries=3,
        )
    elif name == "opportunities":
        # Legacy single-prompt (used by remix)
        agent = Agent(
            model=GoogleModel(_FLASH, provider=provider),
            system_prompt=_MASHUPS_PROMPT,
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

_FAVORITES_PROMPT = """\
You create CLASSIC FAN FAVORITE stickers — the bestsellers. Simple, pretty, \
immediately recognizable. These are what casual fans buy.

Generate 5 concepts. Focus on:
- Ship names in beautiful typography ("Kanthony" in elegant Regency script)
- Character names as identity statements ("Team Benedict", "Penelope Stan")
- Iconic quotes in their original form ("I burn for you", "Dearest Reader")
- Clean aesthetic pieces — the recognizable symbol, logo, or icon
- Pretty visual stickers of beloved characters or objects

These do NOT need puns, internet slang, or cleverness. They need to be \
beautiful, recognizable, and say "I love this thing." \
Typography, elegance, and emotional resonance matter most.

All estimated_appeal should be "broad".

VISUAL SKETCH RULES (critical):
- Name the SPECIFIC character, not "a lady" or "a character"
- Describe their RECOGNIZABLE traits: hair color/style, signature outfit, body language
- Reference the SPECIFIC scene or moment if one is depicted
- Use the fandom's actual color palette and aesthetic
- "Anthony Bridgerton with dark curly hair, white cravat, intense stare" NOT "a Regency gentleman"

For each: concept, exact sticker text, detailed visual sketch, why now, who buys it, emotional hook.\
"""

_MASHUPS_PROMPT = """\
You create WITTY MASHUP stickers — the collision between a fandom's world and \
the internet's current language. These are the ones fans screenshot and send \
to their group chat.

FIRST: Use web_search to find what phrases, slang, and meme formats are \
trending RIGHT NOW on TikTok, Twitter, and Gen Z internet culture. Look for \
the freshest slang — not just "slay" and "no cap" which are already stale.

THEN: Smash those current phrases into the fandom's specific characters, \
scenes, and moments. The humor comes from the CONTRAST — high culture meets \
internet brain, period drama meets shitposting.

Examples of GREAT collisions across different topics:
- TV: "Let [Character] Cook" (character doing their thing + meme format)
- Gaming: "[Game Item] Is My Emotional Support" (item + therapy speak)
- Brand: "No Icks, Just [Brand Icon]" (brand symbol + dating discourse)
- Event: "[Event] Was My Roman Empire" (experience + trend)
- Place: "[Place] Gave Me My Villain Origin Story" (shared experience + meme)
- Subculture: "Unhinged [Subculture] Energy" (identity + energy format)

What makes these work:
- The topic element is SPECIFIC to THIS universe (a character, a scene, an icon — not generic)
- The internet element is CURRENT (search for what's trending NOW, not last year)
- The collision is FUNNY because of the contrast or unexpected pairing
- The text is SHORT enough to read on a 3-inch sticker

Generate 6 concepts. Each MUST name the specific fandom element AND the \
specific internet phrase being crossed.

All estimated_appeal should be "fandom".

VISUAL SKETCH RULES (critical):
- Name the SPECIFIC character, not "a person" or "a figure"
- Describe their RECOGNIZABLE traits: hair, outfit, pose from a known scene
- If the sticker references a specific moment, describe that moment's visual
- "Chibi Zuko with his scar, fire nation armor, brooding expression" NOT "an anime boy"

For each: concept, exact sticker text, detailed visual sketch, why now, who buys it, emotional hook.\
"""

_DEEP_CUTS_PROMPT = """\
You create DEEP CUT stickers — for hardcore fans and subreddit regulars only. \
These signal "I am DEEP in this fandom."

Generate 4 concepts. Focus on:
- Niche scene references that only dedicated fans would recognize
- Community in-jokes from Reddit/TikTok/Twitter discourse
- Specific character moments that sparked intense discussion
- Callbacks to obscure but beloved details
- The kind of thing that makes a fan point at your laptop and say "WAIT you know about THAT?!"

These should be obscure enough that casual fans wouldn't get them, but \
immediately recognizable to anyone in the community.

All estimated_appeal should be "deep_cut".

VISUAL SKETCH RULES (critical):
- Name the SPECIFIC character and their recognizable visual traits
- Reference the EXACT scene, moment, or detail being called back
- These should be visually recognizable to fans even without the text
- "Sokka holding his boomerang with a cactus juice cup" NOT "a warrior with a weapon"

For each: concept, exact sticker text, detailed visual sketch, why now, who buys it, emotional hook.\
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
    """Gather evidence for each entity/moment.

    Runs sequentially on purpose: ``run_research`` is already invoked from a
    worker thread (FastAPI). Nested ThreadPoolExecutor + shared cached Agents
    caused asyncio/event-loop errors and stuck requests when multiple threads
    called ``run_sync`` on the same provider.
    """
    del max_workers  # kept for API compatibility
    targets = entities[:max_entities]
    results: list[EntityEvidence] = []
    for entity in targets:
        ev = _gather_one(entity, topic)
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

def _run_opp_tier(tier_name: str, context: str) -> list[StickerOpportunity]:
    """Run one opportunity tier agent."""
    agent = _get_agent(tier_name)
    try:
        result = _retry(lambda: agent.run_sync(
            f"Generate sticker concepts:\n\n{context}"
        ))
        return result.output
    except Exception as e:
        print(f"  ⚠ {tier_name} failed: {e}", file=sys.stderr)
        return []


def generate_opportunities(
    universe: UniverseMap,
    insights: list[CulturalInsight],
) -> list[StickerOpportunity]:
    """Run 3 focused prompts and merge results (sequential — see gather_evidence_parallel)."""
    context = json.dumps({
        "universe": universe.model_dump(),
        "insights": [i.model_dump() for i in insights],
    }, indent=2, ensure_ascii=False)

    tiers = ["opps_favorites", "opps_mashups", "opps_deep"]
    all_opps: list[StickerOpportunity] = []
    for tier in tiers:
        results = _run_opp_tier(tier, context)
        print(f"  ✓ {tier}: {len(results)} concepts", file=sys.stderr)
        all_opps.extend(results)

    return all_opps


# ---------------------------------------------------------------------------
# Optional: feed in our existing miners for richer evidence
# ---------------------------------------------------------------------------

def _mine_supplementary(topic: str, universe: UniverseMap | None = None) -> str:
    """Run Reddit + YouTube miners using universe context. Best-effort."""
    parts = []
    try:
        from miners.reddit_miner import mine_multiple_subreddits

        # Use universe-discovered subreddits if available
        subreddits = []
        if universe:
            for hub in universe.community_hubs:
                h = hub.strip()
                if h.startswith("r/"):
                    subreddits.append(h[2:])
                elif h.startswith("/r/"):
                    subreddits.append(h[3:])
        # Fallback: guess from topic name
        if not subreddits:
            subreddits = [topic.lower().replace(" ", "")]
        # Cap at 4 subreddits to stay within rate limits
        subreddits = subreddits[:4]

        reddit = mine_multiple_subreddits(
            subreddits, limit=10, include_comments=True, max_comment_posts=5
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

    try:
        from miners.tiktok_miner import mine_tiktok
        # Use universe-discovered hashtags/search terms if available
        tiktok_queries = [topic]
        if universe:
            # Add entity names as additional TikTok searches
            for entity in universe.entities[:3]:
                q = f"{topic} {entity}"
                if q not in tiktok_queries:
                    tiktok_queries.append(q)

        for q in tiktok_queries[:2]:  # cap at 2 searches to keep it fast
            tt = mine_tiktok(q, limit=10, timeout_ms=20_000)
            for r in tt.get("results", [])[:5]:
                views = r.get("view_count", r.get("view_count_numeric", "?"))
                caption = r.get("caption", r.get("text", ""))[:80]
                handle = r.get("handle", "")
                parts.append(f"[TikTok {views} views @{handle}] {caption}")
            if tt.get("warnings"):
                parts.append(f"[TikTok note: {tt['warnings'][0][:80]}]")
    except Exception as e:
        parts.append(f"[TikTok: skipped — {str(e)[:60]}]")

    return "\n".join(parts[:50])  # cap at 50 lines


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
            miner_context = _mine_supplementary(topic, universe=universe)
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
