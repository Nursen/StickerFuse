"""Mine trending posts from Reddit using public JSON endpoints.

Reddit discontinued self-service API keys in Nov 2025. This miner uses
the public .json endpoints (append .json to any Reddit URL) which require
no credentials. Rate limit is ~10 requests/minute.

Usage:
  python -m miners.reddit_miner --subreddits taylorswift nba --limit 20
  python -m miners.reddit_miner --subreddits memes --sort top --time-filter week -o output/reddit.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

_USER_AGENT = "StickerFuse/0.1 (educational project)"
_REQUEST_DELAY = 2.0  # seconds between requests to stay under rate limit


def _fetch_json(url: str) -> dict:
    """Fetch JSON from a Reddit .json endpoint."""
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"Reddit returned {e.code} for {url}: {e.reason}") from e


def mine_subreddit(
    subreddit_name: str,
    *,
    limit: int = 25,
    sort: str = "hot",
    time_filter: str = "week",
) -> dict:
    """Fetch trending posts from a subreddit via public JSON endpoint.

    Args:
        subreddit_name: Name of the subreddit (without r/).
        limit: Number of posts to fetch (max 100 per request).
        sort: Sort method — "hot", "top", "rising", "new".
        time_filter: Time filter for "top" sort — "hour", "day", "week", "month", "year", "all".

    Returns:
        Dict with subreddit info and posts.
    """
    limit = min(limit, 100)

    if sort == "top":
        url = f"https://www.reddit.com/r/{subreddit_name}/top.json?t={time_filter}&limit={limit}"
    else:
        url = f"https://www.reddit.com/r/{subreddit_name}/{sort}.json?limit={limit}"

    data = _fetch_json(url)
    children = data.get("data", {}).get("children", [])

    posts = []
    for child in children:
        d = child.get("data", {})

        if d.get("stickied"):
            continue

        created_dt = datetime.fromtimestamp(
            d.get("created_utc", 0), tz=timezone.utc
        )
        created_iso = created_dt.isoformat()

        # Computed engagement fields
        hours_ago = max(
            (datetime.now(tz=timezone.utc) - created_dt).total_seconds() / 3600,
            0.1,  # floor to avoid division by zero
        )
        score = d.get("score", 0)
        num_comments = d.get("num_comments", 0)

        post = {
            "title": d.get("title", ""),
            "score": score,
            "upvote_ratio": d.get("upvote_ratio", 0),
            "num_comments": num_comments,
            "url": f"https://reddit.com{d.get('permalink', '')}",
            "created_utc": created_iso,
            "selftext_preview": (d.get("selftext") or "")[:300],
            "link_flair_text": d.get("link_flair_text"),
            "is_self": d.get("is_self", False),
            # Computed metrics
            "hours_ago": round(hours_ago, 2),
            "engagement_velocity": round(score / hours_ago, 2),
            "comments_per_hour": round(num_comments / hours_ago, 2),
        }
        posts.append(post)

    return {
        "subreddit": subreddit_name,
        "sort": sort,
        "time_filter": time_filter if sort == "top" else None,
        "post_count": len(posts),
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "posts": posts,
    }


def mine_multiple_subreddits(
    subreddit_names: list[str],
    **kwargs,
) -> dict:
    """Mine multiple subreddits and combine results."""
    results = []
    for i, name in enumerate(subreddit_names):
        print(f"Mining r/{name}...", file=sys.stderr)
        results.append(mine_subreddit(name, **kwargs))
        # Rate limit: wait between requests (skip after last one)
        if i < len(subreddit_names) - 1:
            time.sleep(_REQUEST_DELAY)

    return {
        "source": "reddit",
        "subreddit_count": len(results),
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "subreddits": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine trending Reddit posts (no API key needed)")
    parser.add_argument(
        "--subreddits", nargs="+", required=True,
        help="Subreddit names to mine (e.g. taylorswift nba memes)",
    )
    parser.add_argument("--limit", type=int, default=25, help="Posts per subreddit (default: 25, max: 100)")
    parser.add_argument(
        "--sort", choices=["hot", "top", "rising", "new"], default="hot",
        help="Sort method (default: hot)",
    )
    parser.add_argument(
        "--time-filter", choices=["hour", "day", "week", "month", "year", "all"],
        default="week", help="Time filter for 'top' sort (default: week)",
    )
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON output here")
    args = parser.parse_args()

    result = mine_multiple_subreddits(
        args.subreddits,
        limit=args.limit,
        sort=args.sort,
        time_filter=args.time_filter,
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
