"""Mine trending posts from Reddit using PRAW (official Reddit API).

Fetches hot posts from specified subreddits, extracts titles, scores, comment counts,
and top comments — the raw signal the subtopic agent uses to identify trends.

Setup:
  1. Create a Reddit app at https://www.reddit.com/prefs/apps (select "script")
  2. Add credentials to .env (see .env.example)

Usage:
  python -m miners.reddit_miner --subreddits taylorswift nba --limit 20
  python -m miners.reddit_miner --subreddits memes --time-filter week -o output/reddit.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _build_reddit():
    """Build a PRAW Reddit instance from .env credentials."""
    import praw

    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "StickerFuse/0.1")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env. "
            "Create a Reddit app at https://www.reddit.com/prefs/apps"
        )

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


def mine_subreddit(
    subreddit_name: str,
    *,
    limit: int = 25,
    sort: str = "hot",
    time_filter: str = "week",
    include_comments: bool = True,
    max_comments: int = 5,
) -> dict:
    """Fetch trending posts from a subreddit.

    Args:
        subreddit_name: Name of the subreddit (without r/).
        limit: Number of posts to fetch.
        sort: Sort method — "hot", "top", "rising", "new".
        time_filter: Time filter for "top" sort — "hour", "day", "week", "month", "year", "all".
        include_comments: Whether to fetch top comments per post.
        max_comments: Max comments to fetch per post.

    Returns:
        Dict with subreddit info and posts.
    """
    reddit = _build_reddit()
    subreddit = reddit.subreddit(subreddit_name)

    if sort == "hot":
        submissions = subreddit.hot(limit=limit)
    elif sort == "top":
        submissions = subreddit.top(time_filter=time_filter, limit=limit)
    elif sort == "rising":
        submissions = subreddit.rising(limit=limit)
    elif sort == "new":
        submissions = subreddit.new(limit=limit)
    else:
        submissions = subreddit.hot(limit=limit)

    posts = []
    for submission in submissions:
        if submission.stickied:
            continue

        post = {
            "title": submission.title,
            "score": submission.score,
            "upvote_ratio": submission.upvote_ratio,
            "num_comments": submission.num_comments,
            "url": f"https://reddit.com{submission.permalink}",
            "created_utc": datetime.fromtimestamp(
                submission.created_utc, tz=timezone.utc
            ).isoformat(),
            "selftext_preview": (submission.selftext or "")[:300],
            "link_flair_text": submission.link_flair_text,
            "is_self": submission.is_self,
        }

        if include_comments and submission.num_comments > 0:
            submission.comment_sort = "top"
            submission.comments.replace_more(limit=0)
            top_comments = []
            for comment in submission.comments[:max_comments]:
                top_comments.append({
                    "body": comment.body[:200],
                    "score": comment.score,
                })
            post["top_comments"] = top_comments

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
    for name in subreddit_names:
        print(f"Mining r/{name}...", file=sys.stderr)
        results.append(mine_subreddit(name, **kwargs))

    return {
        "source": "reddit",
        "subreddit_count": len(results),
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "subreddits": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine trending Reddit posts")
    parser.add_argument(
        "--subreddits", nargs="+", required=True,
        help="Subreddit names to mine (e.g. taylorswift nba memes)",
    )
    parser.add_argument("--limit", type=int, default=25, help="Posts per subreddit (default: 25)")
    parser.add_argument(
        "--sort", choices=["hot", "top", "rising", "new"], default="hot",
        help="Sort method (default: hot)",
    )
    parser.add_argument(
        "--time-filter", choices=["hour", "day", "week", "month", "year", "all"],
        default="week", help="Time filter for 'top' sort (default: week)",
    )
    parser.add_argument("--no-comments", action="store_true", help="Skip fetching comments")
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON output here")
    args = parser.parse_args()

    result = mine_multiple_subreddits(
        args.subreddits,
        limit=args.limit,
        sort=args.sort,
        time_filter=args.time_filter,
        include_comments=not args.no_comments,
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
