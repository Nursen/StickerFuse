"""Mine Wikipedia pageview data to detect trending topics.

Uses the Wikimedia Pageviews API (free, no auth) to find spikes in article
views — a strong signal that something is going viral.

Usage:
  python -m miners.wikipedia_miner "Taylor Swift" --limit 5
  python -m miners.wikipedia_miner "NBA playoffs" -o output/wikipedia.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

_USER_AGENT = "StickerFuse/0.1 (educational project; contact: nursen@example.com)"


def _fetch_json(url: str) -> dict:
    """Fetch JSON from a URL with proper User-Agent (required by Wikimedia)."""
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"Wikimedia API returned {e.code} for {url}: {e.reason}") from e


# ---------------------------------------------------------------------------
# Article pageviews
# ---------------------------------------------------------------------------

def get_article_pageviews(article: str, days: int = 30) -> dict:
    """Get daily pageview counts for a Wikipedia article over the last N days.

    Args:
        article: Wikipedia article title (e.g. "Taylor_Swift" or "Taylor Swift").
                 Spaces are converted to underscores automatically.
        days: Number of days to analyze (default: 30).

    Returns:
        Dict with total views, averages, spike detection, and daily breakdown.
    """
    article_clean = article.replace(" ", "_")
    # URL-encode the article title for the API path (handle special chars)
    article_encoded = quote(article_clean, safe="")

    now = datetime.now(tz=timezone.utc)
    # End date is yesterday (today's data may be incomplete)
    end_date = (now - timedelta(days=1))
    start_date = (now - timedelta(days=days))

    start_str = start_date.strftime("%Y%m%d") + "00"
    end_str = end_date.strftime("%Y%m%d") + "00"

    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"en.wikipedia/all-access/all-agents/{article_encoded}/daily/{start_str}/{end_str}"
    )

    data = _fetch_json(url)
    items = data.get("items", [])

    if not items:
        return {
            "article": article_clean,
            "source": "wikipedia_pageviews",
            "days_analyzed": days,
            "total_views": 0,
            "avg_daily_views": 0,
            "peak_day": None,
            "current_day_views": 0,
            "spike_ratio": 0.0,
            "trend_direction": "no_data",
            "daily_views": [],
        }

    # Build daily views list
    daily_views = []
    for item in items:
        ts = item.get("timestamp", "")
        # timestamp format: YYYYMMDD00
        date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        views = item.get("views", 0)
        daily_views.append({"date": date_str, "views": views})

    total_views = sum(d["views"] for d in daily_views)
    avg_daily_views = round(total_views / len(daily_views), 2) if daily_views else 0

    # Peak day
    peak = max(daily_views, key=lambda d: d["views"])

    # Current day views (most recent in the data)
    current_day_views = daily_views[-1]["views"] if daily_views else 0

    # Spike ratio: last 3 days avg vs overall avg
    last_3 = daily_views[-3:] if len(daily_views) >= 3 else daily_views
    last_3_avg = sum(d["views"] for d in last_3) / len(last_3) if last_3 else 0
    spike_ratio = round(last_3_avg / avg_daily_views, 2) if avg_daily_views > 0 else 0.0

    # Trend direction: last 3 days vs previous 3 days
    trend_direction = "steady"
    if len(daily_views) >= 6:
        prev_3 = daily_views[-6:-3]
        prev_3_avg = sum(d["views"] for d in prev_3) / len(prev_3)
        if prev_3_avg > 0:
            ratio = last_3_avg / prev_3_avg
            if ratio > 1.1:
                trend_direction = "rising"
            elif ratio < 0.9:
                trend_direction = "falling"

    return {
        "article": article_clean,
        "source": "wikipedia_pageviews",
        "days_analyzed": days,
        "total_views": total_views,
        "avg_daily_views": avg_daily_views,
        "peak_day": peak,
        "current_day_views": current_day_views,
        "spike_ratio": spike_ratio,
        "trend_direction": trend_direction,
        "daily_views": daily_views,
    }


# ---------------------------------------------------------------------------
# Search + trend check
# ---------------------------------------------------------------------------

def search_wikipedia_trends(query: str, limit: int = 5, days: int = 30) -> dict:
    """Search Wikipedia for articles related to a query and check their pageview trends.

    Uses the Wikipedia search API to find relevant articles, then fetches
    pageview data for each to detect spikes.

    Args:
        query: Search term.
        limit: Max number of articles to analyze.

    Returns:
        Dict with trending article data.
    """
    # Step 1: Search for relevant Wikipedia articles
    search_params = urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    })
    search_url = f"https://en.wikipedia.org/w/api.php?{search_params}"
    search_data = _fetch_json(search_url)

    search_results = search_data.get("query", {}).get("search", [])
    if not search_results:
        return {
            "source": "wikipedia_pageviews",
            "query": query,
            "mined_at": datetime.now(tz=timezone.utc).isoformat(),
            "articles": [],
        }

    # Step 2: Get pageview data for each article
    articles = []
    for result in search_results:
        title = result.get("title", "")
        print(f"  Checking pageviews for: {title}", file=sys.stderr)

        try:
            pv = get_article_pageviews(title, days=days)
        except RuntimeError as e:
            # Some articles may not have pageview data (redirects, etc.)
            print(f"  Skipping {title}: {e}", file=sys.stderr)
            continue

        articles.append({
            "title": title,
            "total_views_30d": pv["total_views"],
            "avg_daily_views": pv["avg_daily_views"],
            "spike_ratio": pv["spike_ratio"],
            "trend_direction": pv["trend_direction"],
            "peak_day": pv["peak_day"],
            "url": f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}",
        })

    # Sort by spike_ratio descending — most spiking articles first
    articles.sort(key=lambda a: a["spike_ratio"], reverse=True)

    return {
        "source": "wikipedia_pageviews",
        "query": query,
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mine Wikipedia pageviews to detect trending topics (no API key needed)",
    )
    parser.add_argument("query", help="Search query (e.g. 'Taylor Swift')")
    parser.add_argument("--limit", type=int, default=5, help="Max articles to analyze (default: 5)")
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON output here")
    args = parser.parse_args()

    print(f"Searching Wikipedia for '{args.query}'...", file=sys.stderr)
    result = search_wikipedia_trends(args.query, limit=args.limit)

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
