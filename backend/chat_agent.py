"""PydanticAI chat agent with StickerFuse pipeline tools.

The agent uses Gemini (via GoogleModel/GoogleProvider) and has tools
that delegate to the existing pipeline agents and miners.

The agent is built lazily on first use so the server can start
even before API keys are configured.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

_executor = ThreadPoolExecutor(max_workers=4)


async def _run_in_thread(fn, *args, **kwargs):
    """Run a sync function in a thread to avoid event loop conflicts."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor, functools.partial(fn, *args, **kwargs)
    )

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

SYSTEM_PROMPT = """\
You are StickerFuse -- an AI assistant that helps users explore trending topics, \
discover viral moments, and generate sticker designs for print-on-demand platforms \
like Redbubble and Etsy.

IMPORTANT: You are DATA-DRIVEN. Every trend claim must be backed by verifiable metrics.

You have access to a full creative pipeline:
1. **Analyze Trends** (USE THIS FIRST) -- mines 5 data sources (Reddit, Google Trends, \
   YouTube, Wikipedia pageviews, Gemini web search) and cross-correlates signals. Returns \
   a TrendReport with platform_count, cross_platform_score, and confidence ratings. \
   A trend confirmed on 3+ platforms with spike_score > 1.5 is rated "high" confidence.
2. **Mine Reddit** -- pull hot posts from subreddits (raw data, prefer analyze_trends).
3. **Mine Google Trends** -- see what search queries are spiking (raw data).
4. **Mine YouTube** -- find trending videos with view velocity (raw data).
5. **Mine Wikipedia** -- check pageview spikes for topics (raw data).
6. **Mine Web Search** -- Gemini grounded web search across Twitter/X, TikTok, news, blogs.
7. **Discover Subtopics** -- analyze scored trend data to find sticker-worthy subtopics.
8. **Extract Viral Bites** -- find the exact quotes, phrases, and meme texts people repeat.
9. **Generate Sticker Ideas** -- turn a viral bite into concrete sticker design concepts.
10. **Generate Design Spec** -- produce a detailed image-generation prompt for a sticker idea.
11. **Generate Sticker Image** -- actually create the PNG sticker using Gemini Nano Banana image gen.
12. **Analyze Community** -- paste chat logs, Discord exports, or forum posts and extract \
    recurring phrases, in-jokes, and sticker-worthy moments. Great for niche communities.

When a user mentions a topic, use analyze_trends FIRST to get cross-platform data. \
Present the metrics (spike scores, platform count, confidence, cross_platform_score) \
alongside your analysis. Highlight which platforms confirm the trend. \
Never claim something is trending without numbers to prove it. \
Walk them through the pipeline step by step, summarising what you found at each stage. \
Be concise but enthusiastic -- you're a creative partner, not a lecture bot.

If the user asks for something outside the sticker pipeline, answer helpfully but \
steer the conversation back toward sticker opportunities.\
"""

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# One Agent instance per model name (primary + optional fallback).
_agents_by_model: dict[str, Agent] = {}


# ---------------------------------------------------------------------------
# Tool functions (defined before agent so we can register them at build time)
# ---------------------------------------------------------------------------

async def analyze_trends(
    ctx: RunContext[None],
    subreddits: list[str],
    keywords: list[str] | None = None,
    limit: int = 25,
) -> str:
    """Mine 5 data sources and cross-correlate into a verified TrendReport.

    Mines Reddit, Google Trends, YouTube, Wikipedia pageviews, and Gemini web
    search, then scores all data with cross-platform correlation. Returns
    platform_count, cross_platform_score, and confidence ratings per trend.

    This is the PRIMARY tool for trend discovery. Use this FIRST.

    Args:
        subreddits: List of subreddit names to mine (without r/).
        keywords: Optional list of Google Trends keywords / YouTube queries.
                  If None, derives search terms from subreddit names.
        limit: Number of posts per subreddit (default 25).
    """
    from miners.reddit_miner import mine_multiple_subreddits
    from miners.trend_scorer import score_trends

    # Derive search terms from keywords or subreddit names
    search_terms = keywords or [s.replace("_", " ") for s in subreddits[:3]]

    # 1. Mine Reddit
    reddit_data = None
    try:
        reddit_data = await _run_in_thread(
            mine_multiple_subreddits, subreddits, limit=limit
        )
    except Exception as exc:
        reddit_data = {"subreddits": []}

    # 2. Mine Google Trends
    trends_data = None
    if search_terms:
        try:
            from miners.trends_miner import mine_multiple_keywords
            trends_data = await _run_in_thread(mine_multiple_keywords, search_terms)
        except Exception:
            trends_data = None

    # 3. Mine YouTube
    youtube_data = None
    try:
        from miners.youtube_miner import mine_youtube
        # Use first search term for YouTube
        youtube_data = await _run_in_thread(
            mine_youtube, search_terms[0], limit=10
        )
    except Exception:
        youtube_data = None

    # 4. Mine Wikipedia pageviews
    wikipedia_data = None
    try:
        from miners.wikipedia_miner import search_wikipedia_trends
        wikipedia_data = await _run_in_thread(
            search_wikipedia_trends, search_terms[0], limit=5
        )
    except Exception:
        wikipedia_data = None

    # 5. Mine web search (Gemini grounding)
    web_search_data = None
    try:
        from miners.web_search_miner import mine_web_search
        web_search_data = await _run_in_thread(
            mine_web_search, f"{search_terms[0]} trending"
        )
    except Exception:
        web_search_data = None

    # Score with cross-platform correlation
    try:
        report = await _run_in_thread(
            score_trends,
            reddit_data,
            trends_data,
            youtube_data,
            wikipedia_data,
            web_search_data,
        )
        return json.dumps(report.model_dump(), indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Trend scoring failed: {exc}"


async def mine_reddit(
    ctx: RunContext[None],
    subreddits: list[str],
    limit: int = 10,
) -> str:
    """Mine hot posts from Reddit subreddits to discover trending content.

    Prefer analyze_trends for scored data. Use this for raw post data only.

    Args:
        subreddits: List of subreddit names (without r/).
        limit: Number of posts per subreddit (default 10).
    """
    from miners.reddit_miner import mine_multiple_subreddits

    try:
        result = await _run_in_thread(mine_multiple_subreddits, subreddits, limit=limit)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Reddit mining failed: {exc}"


async def mine_trends(
    ctx: RunContext[None],
    keywords: list[str],
) -> str:
    """Mine Google Trends data for keywords to see what's spiking in search volume.

    Prefer analyze_trends for scored data. Use this for raw Google Trends data only.

    Args:
        keywords: List of search terms to check trends for.
    """
    from miners.trends_miner import mine_multiple_keywords

    try:
        result = await _run_in_thread(mine_multiple_keywords, keywords)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Trends mining failed: {exc}"


async def mine_youtube_videos(
    ctx: RunContext[None],
    query: str,
    limit: int = 10,
) -> str:
    """Mine trending YouTube videos for a search query.

    Returns video titles, view counts, views per hour, and engagement rates.
    Prefer analyze_trends for cross-correlated data. Use this for raw YouTube data only.

    Args:
        query: Search term (e.g. 'Taylor Swift').
        limit: Max number of videos to return (default 10).
    """
    from miners.youtube_miner import mine_youtube

    try:
        result = await _run_in_thread(mine_youtube, query, limit=limit)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"YouTube mining failed: {exc}"


async def mine_wikipedia(
    ctx: RunContext[None],
    query: str,
    limit: int = 5,
) -> str:
    """Check Wikipedia pageview spikes for a topic.

    Returns spike ratios (recent vs baseline), trend direction, and daily views.
    A spike_ratio > 1.5 indicates significant increased interest. No API key needed.
    Prefer analyze_trends for cross-correlated data.

    Args:
        query: Topic to search for (e.g. 'Taylor Swift').
        limit: Max number of articles to analyze (default 5).
    """
    from miners.wikipedia_miner import search_wikipedia_trends

    try:
        result = await _run_in_thread(search_wikipedia_trends, query, limit=limit)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Wikipedia mining failed: {exc}"


async def mine_web_search(
    ctx: RunContext[None],
    query: str,
) -> str:
    """Search the web for trend signals using Gemini's grounded web search.

    Acts as a meta-source: searches across Twitter/X, TikTok, news, blogs via
    Gemini grounding. Returns URLs with platform detection and relevance.
    Prefer analyze_trends for cross-correlated data.

    Args:
        query: Topic/query to search (e.g. 'Taylor Swift trending moments').
    """
    from miners.web_search_miner import mine_web_search as _mine_ws

    try:
        result = await _run_in_thread(_mine_ws, query)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Web search mining failed: {exc}"


async def discover_subtopics(
    ctx: RunContext[None],
    topic: str,
    trend_report: dict | None = None,
) -> str:
    """Analyze scored trend data to find sticker-worthy subtopics.

    Best used AFTER analyze_trends — pass the TrendReport dict as trend_report.

    Args:
        topic: The cultural topic to explore (e.g. 'Taylor Swift', 'NBA playoffs').
        trend_report: Optional TrendReport dict from analyze_trends.
    """
    from agents.subtopic_agent import discover_subtopics as _discover

    try:
        result = await _run_in_thread(_discover, topic, trend_report=trend_report)
        return json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Subtopic discovery failed: {exc}"


async def extract_viral_bites(
    ctx: RunContext[None],
    subtopic: str,
    context: str = "",
) -> str:
    """Extract the exact viral quotes, phrases, and meme texts from a subtopic.

    Args:
        subtopic: The specific subtopic to mine for viral bites.
        context: Parent topic for additional context.
    """
    from agents.viral_bite_agent import extract_viral_bites as _extract

    try:
        result = await _run_in_thread(_extract, subtopic, context=context)
        return json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Viral bite extraction failed: {exc}"


async def generate_sticker_ideas(
    ctx: RunContext[None],
    viral_bite: str,
    context: str = "",
) -> str:
    """Generate 3-5 sticker design concepts from a viral bite.

    Args:
        viral_bite: The viral text/phrase to design stickers for.
        context: Cultural context for better designs.
    """
    from agents.sticker_idea_agent import generate_sticker_ideas as _generate

    try:
        result = await _run_in_thread(_generate, viral_bite, context=context)
        return json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Sticker idea generation failed: {exc}"


async def generate_design_spec(
    ctx: RunContext[None],
    concept: str,
    style: str = "",
) -> str:
    """Generate a detailed image-generation prompt (design spec) for a sticker concept.

    Args:
        concept: The sticker concept description.
        style: Art style preference (e.g. 'kawaii', 'retro', 'minimalist').
    """
    from agents.design_agent import generate_design_spec as _design

    try:
        result = await _run_in_thread(_design, concept, art_style=style)
        return json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Design spec generation failed: {exc}"


async def generate_sticker_image(
    ctx: RunContext[None],
    prompt: str,
) -> str:
    """Generate a sticker PNG image from a text prompt using Gemini Nano Banana.

    Call this AFTER generating a design spec to actually produce the image.
    Returns the file path where the sticker was saved.

    Args:
        prompt: The image generation prompt (use the image_prompt from a design spec).
    """
    from agents.image_gen_agent import generate_sticker_image as _gen_image

    try:
        path = await _run_in_thread(_gen_image, prompt)
        return f"Sticker image saved to: {path}"
    except Exception as exc:
        return f"Image generation failed: {exc}"


async def analyze_community(
    ctx: RunContext[None],
    text: str,
) -> str:
    """Analyze community text (chat logs, Discord exports, forum posts) for recurring
    phrases, in-jokes, and sticker-worthy moments.

    Paste raw community text and this tool will:
    1. Mine for recurring phrases and emoji patterns (free, instant via VADER)
    2. Run AI interpretation to identify sticker opportunities (cheap, Gemini Flash-Lite)

    Args:
        text: Raw community text to analyze.
    """
    from miners.community_miner import mine_community_text
    from agents.community_agent import analyze_community_text

    # Step 1: Mine for patterns (instant, free)
    mined = await _run_in_thread(mine_community_text, text)

    # Step 2: AI interpretation (cheap, Gemini Flash-Lite)
    analysis = await _run_in_thread(analyze_community_text, mined)

    return json.dumps(
        {
            "mining_results": mined,
            "ai_analysis": analysis.model_dump() if hasattr(analysis, "model_dump") else analysis,
        },
        indent=2,
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Lazy agent builder
# ---------------------------------------------------------------------------

_TOOLS = [
    analyze_trends,
    mine_reddit,
    mine_trends,
    mine_youtube_videos,
    mine_wikipedia,
    mine_web_search,
    discover_subtopics,
    extract_viral_bites,
    generate_sticker_ideas,
    generate_design_spec,
    generate_sticker_image,
    analyze_community,
]


def get_agent(model_name: str | None = None) -> Agent:
    """Build the chat agent for a given model (cached; requires GEMINI_API_KEY)."""
    name = (model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")).strip()
    if name in _agents_by_model:
        return _agents_by_model[name]

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")

    provider = GoogleProvider(api_key=api_key)
    model = GoogleModel(name, provider=provider)

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        output_type=str,
    )

    for fn in _TOOLS:
        agent.tool(fn)

    _agents_by_model[name] = agent
    return agent


async def run_chat_with_retries(user_prompt: str):
    """Run the main chat agent with retries and optional model fallback."""
    from utils.llm_retry import async_retry_llm, is_transient_gemini_error

    primary = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    fallback = os.getenv("GEMINI_MODEL_FALLBACK", "").strip()

    async def run_one(model: str):
        ag = get_agent(model)
        return await async_retry_llm(lambda: ag.run(user_prompt))

    try:
        return await run_one(primary)
    except Exception as e:
        if fallback and fallback != primary and is_transient_gemini_error(e):
            return await run_one(fallback)
        raise
