"""Mine trending search data from Google Trends using pytrends.

Fetches interest over time, related queries (rising & top), and related topics
for a given keyword — confirming what's actually spiking in search volume.

No API key needed — pytrends uses the public Google Trends interface.

Usage:
  python -m miners.trends_miner "Taylor Swift"
  python -m miners.trends_miner "NBA playoffs" --timeframe "now 7-d" -o output/trends.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pytrends.request import TrendReq


def mine_trends(
    keyword: str,
    *,
    timeframe: str = "now 7-d",
    geo: str = "US",
) -> dict:
    """Fetch Google Trends data for a keyword.

    Args:
        keyword: Search term to analyze.
        timeframe: Pytrends timeframe string.
            - "now 1-H" = last hour
            - "now 4-H" = last 4 hours
            - "now 1-d" = last day
            - "now 7-d" = last 7 days
            - "today 1-m" = last 30 days
            - "today 3-m" = last 90 days
        geo: Country code (default: US).

    Returns:
        Dict with interest over time, related queries, and related topics.
    """
    pytrends = TrendReq(hl="en-US", tz=360)
    pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo=geo)

    # Interest over time
    interest_df = pytrends.interest_over_time()
    interest_data = []
    if not interest_df.empty and keyword in interest_df.columns:
        for date, row in interest_df.iterrows():
            interest_data.append({
                "date": date.isoformat(),
                "interest": int(row[keyword]),
            })

    # Related queries
    related_queries_raw = pytrends.related_queries()
    rising_queries = []
    top_queries = []
    if keyword in related_queries_raw:
        kw_data = related_queries_raw[keyword]
        if kw_data.get("rising") is not None and not kw_data["rising"].empty:
            for _, row in kw_data["rising"].head(15).iterrows():
                rising_queries.append({
                    "query": row["query"],
                    "value": str(row["value"]),
                })
        if kw_data.get("top") is not None and not kw_data["top"].empty:
            for _, row in kw_data["top"].head(15).iterrows():
                top_queries.append({
                    "query": row["query"],
                    "value": int(row["value"]),
                })

    # Related topics
    related_topics_raw = pytrends.related_topics()
    rising_topics = []
    top_topics = []
    if keyword in related_topics_raw:
        t_data = related_topics_raw[keyword]
        if t_data.get("rising") is not None and not t_data["rising"].empty:
            for _, row in t_data["rising"].head(10).iterrows():
                rising_topics.append({
                    "title": row.get("topic_title", ""),
                    "type": row.get("topic_type", ""),
                    "value": str(row.get("value", "")),
                })
        if t_data.get("top") is not None and not t_data["top"].empty:
            for _, row in t_data["top"].head(10).iterrows():
                top_topics.append({
                    "title": row.get("topic_title", ""),
                    "type": row.get("topic_type", ""),
                    "value": int(row.get("value", 0)),
                })

    return {
        "source": "google_trends",
        "keyword": keyword,
        "timeframe": timeframe,
        "geo": geo,
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "interest_over_time": interest_data,
        "related_queries": {
            "rising": rising_queries,
            "top": top_queries,
        },
        "related_topics": {
            "rising": rising_topics,
            "top": top_topics,
        },
    }


def mine_multiple_keywords(
    keywords: list[str],
    **kwargs,
) -> dict:
    """Mine trends for multiple keywords."""
    results = []
    for kw in keywords:
        print(f"Mining Google Trends for: {kw}", file=sys.stderr)
        results.append(mine_trends(kw, **kwargs))

    return {
        "source": "google_trends",
        "keyword_count": len(results),
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "keywords": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine Google Trends data")
    parser.add_argument(
        "keywords", nargs="+",
        help="Keywords to search (e.g. 'Taylor Swift' 'NBA playoffs')",
    )
    parser.add_argument(
        "--timeframe", default="now 7-d",
        help="Pytrends timeframe (default: 'now 7-d')",
    )
    parser.add_argument("--geo", default="US", help="Country code (default: US)")
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON output here")
    args = parser.parse_args()

    result = mine_multiple_keywords(
        args.keywords,
        timeframe=args.timeframe,
        geo=args.geo,
    )

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
