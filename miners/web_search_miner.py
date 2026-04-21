"""Mine web search results for trend signals using Gemini's grounded web search.

Acts as a meta-source: searches across Twitter/X, TikTok, news, blogs to find
mentions and discussions about a topic. Uses PydanticAI WebSearchTool (same
pattern as Lecture 18).

Usage:
  python -m miners.web_search_miner "Taylor Swift trending moments"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.builtin_tools import WebSearchTool
from pydantic_ai.messages import (
    BuiltinToolReturnPart,
    ModelResponse,
)
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider

# Load env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
load_dotenv(_PROJECT_ROOT / ".env")

from utils.llm_retry import sync_retry_llm

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Platform detection from URL domains
_PLATFORM_MAP = {
    "twitter.com": "twitter",
    "x.com": "twitter",
    "reddit.com": "reddit",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "pinterest.com": "pinterest",
    "tumblr.com": "tumblr",
    "bbc.com": "news",
    "bbc.co.uk": "news",
    "cnn.com": "news",
    "nytimes.com": "news",
    "reuters.com": "news",
    "apnews.com": "news",
    "theguardian.com": "news",
    "washingtonpost.com": "news",
    "nbcnews.com": "news",
    "foxnews.com": "news",
    "abcnews.go.com": "news",
    "cbsnews.com": "news",
    "usatoday.com": "news",
    "variety.com": "news",
    "billboard.com": "news",
    "rollingstone.com": "news",
    "ew.com": "news",
    "tmz.com": "news",
    "buzzfeed.com": "blog",
    "medium.com": "blog",
    "substack.com": "blog",
    "wordpress.com": "blog",
    "blogspot.com": "blog",
    "wikipedia.org": "wikipedia",
}


def _detect_platform(url: str) -> str:
    """Infer which platform a URL belongs to."""
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        for domain, platform in _PLATFORM_MAP.items():
            if host == domain or host.endswith("." + domain):
                return platform
        return "web"
    except Exception:
        return "web"


def _resolve_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    return key


def _build_agent(*, model_name: str = DEFAULT_MODEL) -> Agent[None, str]:
    """Build a PydanticAI agent with Gemini + WebSearchTool for trend mining."""
    provider = GoogleProvider(api_key=_resolve_api_key())
    model = GoogleModel(model_name, provider=provider)
    settings = GoogleModelSettings(temperature=0.3, max_tokens=4096)

    return Agent(
        model,
        output_type=str,
        model_settings=settings,
        builtin_tools=[WebSearchTool()],
        instructions=(
            "You are a trend research analyst. Use the web_search tool to find "
            "recent viral moments, trending discussions, and social media buzz "
            "about the given topic. Search multiple times if needed to cover "
            "Twitter/X, TikTok, Reddit, news sites, and blogs.\n\n"
            "Important: Do not quote long passages from any site. Paraphrase in your own words "
            "to avoid recitation. Short snippets (under 25 words) are OK.\n\n"
            "After searching, respond with a single JSON object (no markdown fences):\n"
            '{"summary": "2-3 sentence overview of what\'s trending", '
            '"mentions": [{"title": "...", "snippet": "...", "url": "...", '
            '"relevance": "high|medium|low"}]}\n\n'
            "Include up to 15 of the most relevant mentions. Focus on recency "
            "and virality. Each mention should have a real URL from your search results."
        ),
    )


def _extract_grounding_urls(messages: list[Any]) -> list[dict]:
    """Extract URLs from Gemini grounding chunks in web_search tool returns."""
    rows: list[dict] = []
    seen_urls: set[str] = set()
    for msg in messages:
        if not isinstance(msg, ModelResponse):
            continue
        for part in msg.parts:
            if isinstance(part, BuiltinToolReturnPart) and part.tool_name == "web_search":
                content = part.content
                if not isinstance(content, list):
                    continue
                for chunk in content:
                    if not isinstance(chunk, dict):
                        continue
                    uri = chunk.get("uri") or chunk.get("url")
                    if not uri or uri in seen_urls:
                        continue
                    seen_urls.add(uri)
                    rows.append({
                        "url": uri,
                        "title": str(chunk.get("title") or ""),
                        "snippet": str(chunk.get("snippet") or ""),
                        "platform": _detect_platform(uri),
                        "relevance": "medium",
                        "source_type": "grounding_chunk",
                    })
    return rows


def _web_search_empty_result(query: str, now: datetime, err: BaseException) -> dict[str, Any]:
    """Graceful degradation so /api/analyze still completes when Gemini blocks web search."""
    s = str(err).lower()
    blocked = "recitation" in s or "content_filter" in s
    hint = (
        "Gemini blocked grounded output (often for well-known shows/IPs). Other sources still apply."
        if blocked
        else "Web search step failed; other sources still apply."
    )
    return {
        "source": "web_search",
        "query": query,
        "mined_at": now.isoformat(),
        "search_provider": "gemini_google_search_grounding",
        "result_count": 0,
        "results": [],
        "summary": hint,
        "error_sanitized": str(err)[:500],
    }


def _parse_model_output(text: str) -> dict[str, Any]:
    """Parse the model's JSON output, tolerant of markdown fences."""
    raw = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```\s*$", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {"summary": text[:500], "mentions": []}


def mine_web_search(query: str, *, model_name: str = DEFAULT_MODEL) -> dict:
    """Run Gemini grounded web search to find trend signals for a query.

    Args:
        query: The topic/query to search for.
        model_name: Gemini model to use.

    Returns:
        Dict with structured web search results and platform detection.
    """
    now = datetime.now(tz=timezone.utc)
    print(f"Web search mining for '{query}' (model={model_name})...", file=sys.stderr)

    agent = _build_agent(model_name=model_name)

    user_prompt = (
        f"Find recent trending discussions, viral moments, and social media buzz "
        f"about: {query}\n\n"
        f"Search Twitter/X, TikTok, Reddit, news sites, and blogs. "
        f"Focus on content from the last 7 days. Today is {now.strftime('%B %d, %Y')}."
    )

    # Softer follow-up if Gemini blocks with RECITATION / content_filter (common for media IPs)
    fallback_prompt = (
        f"Topic: {query}. Use web_search briefly. In your own words only, give a JSON object "
        f'exactly as instructed with summary and mentions (URLs from results). '
        f"Avoid quoting or closely paraphrasing any single copyrighted passage. "
        f"Today is {now.strftime('%B %d, %Y')}."
    )

    def _is_blocked(exc: BaseException) -> bool:
        s = str(exc).lower()
        return "recitation" in s or "content_filter" in s or "content filter" in s

    run = None
    try:
        run = sync_retry_llm(lambda: agent.run_sync(user_prompt))
    except Exception as first_err:
        if _is_blocked(first_err):
            print(
                f"Web search: first pass blocked ({str(first_err)[:220]}), retrying with fallback prompt...",
                file=sys.stderr,
            )
            try:
                run = sync_retry_llm(lambda: agent.run_sync(fallback_prompt))
            except Exception as second_err:
                print(f"Web search fallback failed: {str(second_err)[:400]}", file=sys.stderr)
                return _web_search_empty_result(query, now, second_err)
        else:
            print(f"Web search failed: {str(first_err)[:400]}", file=sys.stderr)
            return _web_search_empty_result(query, now, first_err)

    if run is None:
        return _web_search_empty_result(query, now, RuntimeError("no model run"))

    try:
        messages = run.all_messages()

        # Get grounding URLs from the raw message exchange
        grounding_results = _extract_grounding_urls(messages)

        # Parse the model's structured output
        out_text = run.output or ""
        parsed = _parse_model_output(out_text)
        summary = parsed.get("summary", "")

        # Merge model mentions with grounding URLs
        model_mentions = parsed.get("mentions", [])
        seen_urls: set[str] = set()
        results: list[dict] = []

        # Model mentions first (tend to be higher quality)
        for mention in model_mentions:
            if not isinstance(mention, dict):
                continue
            url = mention.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append({
                    "url": url,
                    "title": mention.get("title", ""),
                    "snippet": mention.get("snippet", ""),
                    "platform": _detect_platform(url),
                    "relevance": mention.get("relevance", "medium"),
                    "source_type": "model_json",
                })

        # Then grounding URLs the model didn't mention
        for row in grounding_results:
            url = row.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append(row)

        return {
            "source": "web_search",
            "query": query,
            "mined_at": now.isoformat(),
            "search_provider": "gemini_google_search_grounding",
            "result_count": len(results),
            "results": results,
            "summary": summary,
        }
    except Exception as tail_err:
        print(f"Web search post-process failed: {str(tail_err)[:400]}", file=sys.stderr)
        return _web_search_empty_result(query, now, tail_err)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mine web search results for trend signals using Gemini grounding",
    )
    parser.add_argument("query", help="Topic/query to search (e.g. 'Taylor Swift trending')")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model to use")
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON output here")
    args = parser.parse_args()

    result = mine_web_search(args.query, model_name=args.model)

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
