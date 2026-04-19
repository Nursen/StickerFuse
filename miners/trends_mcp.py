"""Mine multi-platform trend data via Trends MCP (12+ sources in one API).

Free tier: 100 requests/day. Covers TikTok hashtag trends, YouTube, Reddit,
Google Search, Wikipedia, News, and more.

Usage:
  python -m miners.trends_mcp "Taylor Swift" --source tiktok
  python -m miners.trends_mcp --top-trends --limit 10
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _get_client():
    """Lazy-import and build the TrendsMcpClient."""
    from tiktok_trends_mcp import TrendsMcpClient

    api_key = os.environ.get("TRENDSMCP_API_KEY")
    if not api_key:
        raise RuntimeError("Set TRENDSMCP_API_KEY in .env (free at trendsmcp.ai)")
    return TrendsMcpClient(api_key=api_key)


def get_trend_timeseries(keyword: str, source: str = "Tiktok") -> dict:
    """Get time-series trend data for a keyword on a platform.

    Args:
        keyword: Search term.
        source: Platform — "Tiktok", "Youtube", "Reddit", "Google", etc.

    Returns dict with time series data, growth rates, etc.
    """
    client = _get_client()
    try:
        result = client.get_trends(source=source, keyword=keyword)
        return {
            "source": "trends_mcp",
            "platform": source,
            "keyword": keyword,
            "mined_at": datetime.now(tz=timezone.utc).isoformat(),
            "data": result if isinstance(result, dict) else str(result),
        }
    except Exception as exc:
        return {
            "source": "trends_mcp",
            "platform": source,
            "keyword": keyword,
            "mined_at": datetime.now(tz=timezone.utc).isoformat(),
            "error": str(exc),
        }


def get_growth_rates(keyword: str, source: str = "Tiktok") -> dict:
    """Get growth percentages over 1W, 1M, 3M, 6M, 1Y periods."""
    client = _get_client()
    try:
        result = client.get_growth(
            source=source,
            keyword=keyword,
            percent_growth=["1W", "1M", "3M", "6M", "12M"],
        )
        return {
            "source": "trends_mcp",
            "platform": source,
            "keyword": keyword,
            "mined_at": datetime.now(tz=timezone.utc).isoformat(),
            "growth": result if isinstance(result, dict) else str(result),
        }
    except Exception as exc:
        return {"source": "trends_mcp", "keyword": keyword, "error": str(exc)}


def get_top_trending(source: str = "Tiktok", limit: int = 10) -> dict:
    """Get what's trending RIGHT NOW on a platform."""
    client = _get_client()
    try:
        result = client.get_top_trends(type=source, limit=limit)
        return {
            "source": "trends_mcp",
            "platform": source,
            "mined_at": datetime.now(tz=timezone.utc).isoformat(),
            "limit": limit,
            "trends": result if isinstance(result, (list, dict)) else str(result),
        }
    except Exception as exc:
        return {"source": "trends_mcp", "platform": source, "error": str(exc)}


def mine_trends_mcp(
    keyword: str,
    sources: list[str] | None = None,
) -> dict:
    """Mine trend data across multiple platforms for a keyword.

    Args:
        keyword: Search term.
        sources: Platforms to check. Defaults to ["Tiktok", "Youtube", "Google"].
    """
    if sources is None:
        sources = ["Tiktok", "Youtube", "Google"]

    results = {}
    for source in sources:
        print(f"Mining Trends MCP ({source}): {keyword}", file=sys.stderr)
        results[source.lower()] = {
            "timeseries": get_trend_timeseries(keyword, source),
            "growth": get_growth_rates(keyword, source),
        }

    # Also get top trends from primary source
    results["top_trending"] = get_top_trending(sources[0])

    return {
        "source": "trends_mcp",
        "keyword": keyword,
        "platforms_queried": sources,
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "results": results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mine multi-platform trend data via Trends MCP (12+ sources)",
    )
    parser.add_argument("keyword", nargs="?", default=None, help="Search term (e.g. 'Taylor Swift')")
    parser.add_argument(
        "--source", nargs="+", default=["Tiktok", "Youtube", "Google"],
        help="Platform(s) to query (default: Tiktok Youtube Google)",
    )
    parser.add_argument(
        "--top-trends", action="store_true",
        help="Just fetch top trending items (no keyword needed)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Limit for top trends (default: 10)")
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON output here")
    args = parser.parse_args()

    if args.top_trends:
        print(f"Fetching top trends from {args.source[0]}...", file=sys.stderr)
        result = get_top_trending(source=args.source[0], limit=args.limit)
    elif args.keyword:
        print(f"Mining trends for '{args.keyword}' across {args.source}...", file=sys.stderr)
        result = mine_trends_mcp(args.keyword, sources=args.source)
    else:
        parser.error("Provide a keyword or use --top-trends")
        return  # unreachable but keeps type checkers happy

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
