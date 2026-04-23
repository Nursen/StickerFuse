"""Iterative research agent — 3-round evidence gathering that refines as it learns.

Unlike the flat research agent which searches for all entities independently,
this agent works like a real research intern:

  Round 1 (Broad): Search top entities/moments in parallel — get the lay of the land
  Round 2 (Refine): Analyze what's interesting, generate refined search queries, search again
  Round 3 (Deep): Targeted deep dives on the hottest/most controversial findings

Then feeds all evidence (R1 + R2 + R3) into insight synthesis and opportunity generation.

Usage:
  python -m agents.iterative_research_agent "Bridgerton"
  python -m agents.iterative_research_agent "Avatar the Last Airbender" --max-per-round 4
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
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

# Reuse existing agent infrastructure
from agents.research_agent import (
    _get_agent,
    _retry,
    map_universe,
    gather_evidence,
    synthesize_insights,
    generate_opportunities,
    _mine_supplementary,
)

_FLASH = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Refinement schema — what Round 2 searches for
# ---------------------------------------------------------------------------

class RefinedQuery(BaseModel):
    """A refined search query based on Round 1 findings."""
    query: str = Field(description="The specific search query to run")
    topic_context: str = Field(description="How this relates to the parent topic")
    why: str = Field(description="Why this is worth investigating — what was surprising or underexplored in Round 1")


class RefinementPlan(BaseModel):
    """Output of the refinement agent — what to search next."""
    surprising_findings: list[str] = Field(
        description="2-4 things from Round 1 that were surprising, controversial, or underexplored"
    )
    refined_queries: list[RefinedQuery] = Field(
        description="4-6 refined search queries to run in Round 2. These should be MORE SPECIFIC "
        "than Round 1 — drill into specific incidents, controversies, memes, or moments."
    )
    deep_dive_candidates: list[str] = Field(
        description="2-3 topics from Round 1 that deserve a deep dive in Round 3 — "
        "the most controversial, viral, or sticker-worthy findings"
    )


class DeepDiveQuery(BaseModel):
    """A targeted deep-dive query for Round 3."""
    query: str = Field(description="Highly specific search query")
    angle: str = Field(description="What angle to investigate: sentiment shift, meme origin, controversy timeline, etc.")


class DeepDivePlan(BaseModel):
    """Output of the deep dive planner — final targeted searches."""
    queries: list[DeepDiveQuery] = Field(
        description="2-3 highly targeted queries for the final round"
    )


# ---------------------------------------------------------------------------
# Refinement agent — analyzes Round 1, plans Round 2
# ---------------------------------------------------------------------------

def _build_model(model_name: str | None = None) -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(model_name or _FLASH, provider=provider)


_refinement_agent = None
_deep_dive_planner = None


def _get_refinement_agent() -> Agent:
    global _refinement_agent
    if _refinement_agent is None:
        _refinement_agent = Agent(
            model=_build_model(),
            system_prompt="""\
You analyze Round 1 research findings and plan refined searches for Round 2.

You receive: a universe map and initial evidence gathered about key entities.

Your job:
1. Identify what was SURPRISING or UNDEREXPLORED — what threads deserve pulling?
2. Generate REFINED search queries that go DEEPER than Round 1:
   - Instead of "Benedict Bridgerton" → "Benedict Sophie mistress proposal backlash"
   - Instead of "Mario" → "Mario movie Chris Pratt voice controversy"
   - Instead of "Owala" → "Owala vs Stanley TikTok color drop drama"
3. Identify 2-3 deep dive candidates for Round 3

Your refined queries should:
- Be MORE SPECIFIC than the original entity names
- Target specific incidents, controversies, memes, or viral moments
- Include community-specific terminology (ship names, abbreviations, slang)
- Focus on things that would make good sticker content (emotional, funny, controversial)\
""",
            output_type=RefinementPlan,
            model_settings=GoogleModelSettings(temperature=0.3, max_tokens=3072),
            retries=3,
        )
    return _refinement_agent


def _get_deep_dive_planner() -> Agent:
    global _deep_dive_planner
    if _deep_dive_planner is None:
        _deep_dive_planner = Agent(
            model=_build_model(),
            system_prompt="""\
You plan the final deep-dive searches (Round 3) based on the most interesting
findings from Rounds 1 and 2.

Focus on:
- The most controversial or divisive findings
- Viral moments with the strongest emotional reactions
- Specific memes, quotes, or phrases that fans are repeating
- Things that would make the BEST sticker content

Generate 2-3 highly targeted queries. Each should investigate a specific angle:
sentiment shift, meme origin, controversy timeline, viral audio source, etc.\
""",
            output_type=DeepDivePlan,
            model_settings=GoogleModelSettings(temperature=0.3, max_tokens=2048),
            retries=3,
        )
    return _deep_dive_planner


# ---------------------------------------------------------------------------
# Parallel evidence gathering helper
# ---------------------------------------------------------------------------

def _gather_one_safe(query: str, topic: str) -> EntityEvidence | None:
    """Gather evidence for a single query, return None on failure."""
    try:
        return gather_evidence(query, topic)
    except Exception as e:
        print(f"  ⚠ Failed: '{query}': {e}", file=sys.stderr)
        return None


def _gather_batch_parallel(
    queries: list[str], topic: str, max_workers: int = 3
) -> list[EntityEvidence]:
    """Gather evidence for multiple queries in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_gather_one_safe, q, topic): q for q in queries}
        for future in as_completed(futures):
            query = futures[future]
            ev = future.result()
            if ev:
                results.append(ev)
                print(f"  ✓ {query[:60]}", file=sys.stderr)
    return results


# ---------------------------------------------------------------------------
# The 3-round pipeline
# ---------------------------------------------------------------------------

def run_iterative_research(
    topic: str,
    max_per_round: int = 4,
    use_miners: bool = True,
    verbose: bool = True,
) -> ResearchReport:
    """Run the iterative 3-round research pipeline.

    Args:
        topic: Any cultural topic
        max_per_round: Max queries per round
        use_miners: Also run Reddit/YouTube/TikTok miners
        verbose: Print progress to stderr
    """

    # Step 1: Universe Mapping (same as flat agent)
    if verbose:
        print(f"Step 1: Mapping the universe of '{topic}'...", file=sys.stderr)
    universe = map_universe(topic)
    if verbose:
        print(f"  {len(universe.entities)} entities, "
              f"{len(universe.iconic_moments)} moments", file=sys.stderr)

    # Supplementary mining (same as flat agent)
    miner_context = ""
    if use_miners:
        if verbose:
            print(f"\nMining Reddit + YouTube + TikTok...", file=sys.stderr)
        try:
            miner_context = _mine_supplementary(topic, universe=universe)
            if verbose and miner_context:
                lines = miner_context.count("\n") + 1
                print(f"  {lines} supplementary data points", file=sys.stderr)
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Round 1: Broad sweep
    # -----------------------------------------------------------------------
    if verbose:
        print(f"\n--- Round 1 (Broad): Top {max_per_round} entities ---", file=sys.stderr)

    # Pick initial targets: moments first (more sticker-worthy), then entities
    targets_r1 = []
    seen = set()
    for item in (universe.iconic_moments + universe.entities):
        key = item.lower().strip()
        if key not in seen:
            seen.add(key)
            targets_r1.append(item)
    targets_r1 = targets_r1[:max_per_round]

    evidence_r1 = _gather_batch_parallel(targets_r1, topic)
    if verbose:
        print(f"  Round 1: {len(evidence_r1)} results", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Round 2: Refine based on what we learned
    # -----------------------------------------------------------------------
    if verbose:
        print(f"\n--- Round 2 (Refine): Analyzing Round 1, generating refined queries ---", file=sys.stderr)

    refinement_context = json.dumps({
        "universe": universe.model_dump(),
        "round1_evidence": [e.model_dump() for e in evidence_r1],
    }, indent=2, ensure_ascii=False)

    agent = _get_refinement_agent()
    plan = _retry(lambda: agent.run_sync(
        f"Analyze Round 1 findings and plan refined searches:\n\n{refinement_context}"
    )).output

    if verbose:
        print(f"  Surprising: {plan.surprising_findings}", file=sys.stderr)
        print(f"  Refined queries: {[q.query for q in plan.refined_queries]}", file=sys.stderr)
        print(f"  Deep dive candidates: {plan.deep_dive_candidates}", file=sys.stderr)

    refined_queries = [q.query for q in plan.refined_queries[:max_per_round]]
    evidence_r2 = _gather_batch_parallel(refined_queries, topic)
    if verbose:
        print(f"  Round 2: {len(evidence_r2)} results", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Round 3: Deep dive on the hottest findings
    # -----------------------------------------------------------------------
    if verbose:
        print(f"\n--- Round 3 (Deep): Targeted deep dives ---", file=sys.stderr)

    all_evidence_so_far = evidence_r1 + evidence_r2
    deep_context = json.dumps({
        "universe": universe.model_dump(),
        "all_evidence": [e.model_dump() for e in all_evidence_so_far],
        "refinement_plan": plan.model_dump(),
    }, indent=2, ensure_ascii=False)

    planner = _get_deep_dive_planner()
    deep_plan = _retry(lambda: planner.run_sync(
        f"Plan final deep-dive searches:\n\n{deep_context}"
    )).output

    deep_queries = [q.query for q in deep_plan.queries[:3]]
    if verbose:
        print(f"  Deep queries: {deep_queries}", file=sys.stderr)

    evidence_r3 = _gather_batch_parallel(deep_queries, topic, max_workers=2)
    if verbose:
        print(f"  Round 3: {len(evidence_r3)} results", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Combine all evidence and synthesize
    # -----------------------------------------------------------------------
    all_evidence = evidence_r1 + evidence_r2 + evidence_r3
    if verbose:
        print(f"\n--- Synthesis: {len(all_evidence)} total evidence pieces ---", file=sys.stderr)

    # Deduplicate by entity name
    seen_entities = set()
    unique_evidence = []
    for ev in all_evidence:
        key = ev.entity.lower().strip()
        if key not in seen_entities:
            seen_entities.add(key)
            unique_evidence.append(ev)
    all_evidence = unique_evidence

    if verbose:
        print(f"  {len(all_evidence)} unique (after dedup)", file=sys.stderr)
        print(f"\nStep 3: Synthesizing cultural insights...", file=sys.stderr)

    insights = synthesize_insights(universe, all_evidence, miner_context=miner_context)
    if verbose:
        print(f"  {len(insights)} insights", file=sys.stderr)
        print(f"\nStep 4: Generating sticker opportunities...", file=sys.stderr)

    opportunities = generate_opportunities(universe, insights)
    if verbose:
        print(f"  {len(opportunities)} opportunities", file=sys.stderr)

    hot = [i for i in insights if i.virality in ("viral", "trending")]
    summary = (
        f"Iterative research on '{topic}': 3 rounds of evidence gathering "
        f"({len(evidence_r1)}+{len(evidence_r2)}+{len(evidence_r3)} → "
        f"{len(all_evidence)} unique). {len(insights)} insights, "
        f"{len(hot)} viral/trending. {len(opportunities)} sticker opportunities."
    )

    return ResearchReport(
        topic=topic,
        universe=universe,
        evidence=all_evidence,
        insights=insights,
        opportunities=opportunities,
        executive_summary=summary,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Iterative research: 3 rounds of evidence gathering"
    )
    parser.add_argument("topic", help="Any cultural topic")
    parser.add_argument("--max-per-round", type=int, default=4)
    parser.add_argument("--no-miners", action="store_true")
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    report = run_iterative_research(
        args.topic, max_per_round=args.max_per_round, use_miners=not args.no_miners
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
