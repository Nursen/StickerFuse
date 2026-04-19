"""Mine trending YouTube videos for a search query.

Uses the YouTube Data API v3 when YOUTUBE_API_KEY is set in .env,
otherwise falls back to the public YouTube RSS feed (no view counts).

Usage:
  python -m miners.youtube_miner "Taylor Swift" --limit 10
  python -m miners.youtube_miner "NBA highlights" -o output/youtube.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

_USER_AGENT = "StickerFuse/0.1 (educational project)"


def _load_api_key() -> str | None:
    """Load YOUTUBE_API_KEY from .env file or environment."""
    key = os.environ.get("YOUTUBE_API_KEY")
    if key:
        return key
    # Try reading .env from project root
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == "YOUTUBE_API_KEY":
                v = v.strip().strip('"').strip("'")
                if v and not v.startswith("your-"):
                    return v
    return None


def _fetch_json(url: str) -> dict:
    """Fetch JSON from a URL."""
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"YouTube API returned {e.code} for {url}: {e.reason}") from e


def _fetch_xml(url: str) -> ET.Element:
    """Fetch and parse XML from a URL."""
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=15) as resp:
            return ET.fromstring(resp.read())
    except HTTPError as e:
        raise RuntimeError(f"YouTube RSS returned {e.code} for {url}: {e.reason}") from e


def _parse_iso_datetime(s: str) -> datetime:
    """Parse ISO 8601 datetime string to timezone-aware datetime."""
    # Handle both 'Z' suffix and '+00:00'
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _hours_since(dt: datetime) -> float:
    """Hours elapsed since the given datetime."""
    delta = (datetime.now(tz=timezone.utc) - dt).total_seconds() / 3600
    return max(delta, 0.1)  # floor to avoid division by zero


# ---------------------------------------------------------------------------
# API-key path: YouTube Data API v3
# ---------------------------------------------------------------------------

def _mine_with_api(query: str, *, limit: int, api_key: str) -> list[dict]:
    """Search and fetch video stats using the YouTube Data API v3."""
    now = datetime.now(tz=timezone.utc)
    published_after = (now - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")

    # Step 1: Search for videos
    search_params = urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "viewCount",
        "publishedAfter": published_after,
        "maxResults": min(limit, 50),
        "key": api_key,
    })
    search_url = f"https://www.googleapis.com/youtube/v3/search?{search_params}"
    search_data = _fetch_json(search_url)

    items = search_data.get("items", [])
    if not items:
        return []

    video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
    if not video_ids:
        return []

    # Step 2: Get detailed stats for each video
    stats_params = urlencode({
        "part": "statistics,snippet",
        "id": ",".join(video_ids),
        "key": api_key,
    })
    stats_url = f"https://www.googleapis.com/youtube/v3/videos?{stats_params}"
    stats_data = _fetch_json(stats_url)

    videos = []
    for item in stats_data.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        video_id = item["id"]

        published_at = _parse_iso_datetime(snippet.get("publishedAt", "2000-01-01T00:00:00Z"))
        hours_ago = _hours_since(published_at)

        view_count = int(stats.get("viewCount", 0))
        like_count = int(stats.get("likeCount", 0))
        comment_count = int(stats.get("commentCount", 0))

        engagement_rate = 0.0
        if view_count > 0:
            engagement_rate = round((like_count + comment_count) / view_count, 6)

        videos.append({
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}",
            "published_at": published_at.isoformat(),
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "hours_ago": round(hours_ago, 2),
            "views_per_hour": round(view_count / hours_ago, 2),
            "engagement_rate": engagement_rate,
        })

    return videos


# ---------------------------------------------------------------------------
# Fallback path: YouTube RSS feed (no API key)
# ---------------------------------------------------------------------------

def _mine_with_rss(query: str, *, limit: int) -> list[dict]:
    """Fall back to the YouTube RSS feed. No view counts available."""
    rss_url = f"https://www.youtube.com/feeds/videos.xml?search_query={quote_plus(query)}"
    root = _fetch_xml(rss_url)

    # Atom namespace
    ns = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}

    entries = root.findall("atom:entry", ns)[:limit]
    videos = []

    for entry in entries:
        title = entry.findtext("atom:title", "", ns)
        author_el = entry.find("atom:author", ns)
        channel = author_el.findtext("atom:name", "", ns) if author_el is not None else ""
        video_link = entry.findtext("atom:link", "", ns)
        # Get video ID from the yt:videoId element
        video_id = entry.findtext("{http://www.youtube.com/xml/schemas/2015}videoId", "")
        published_raw = entry.findtext("atom:published", "", ns)

        published_at = None
        hours_ago = None
        if published_raw:
            published_at = _parse_iso_datetime(published_raw)
            hours_ago = round(_hours_since(published_at), 2)

        videos.append({
            "title": title,
            "channel": channel,
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}" if video_id else "",
            "published_at": published_at.isoformat() if published_at else None,
            "view_count": None,
            "like_count": None,
            "comment_count": None,
            "hours_ago": hours_ago,
            "views_per_hour": None,
            "engagement_rate": None,
        })

    return videos


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def mine_youtube(query: str, *, limit: int = 15, api_key: str | None = None) -> dict:
    """Mine trending YouTube videos for a query.

    Args:
        query: Search term.
        limit: Max number of videos to return.
        api_key: YouTube Data API v3 key. If None, tries .env / env var,
                 then falls back to RSS (no stats).

    Returns:
        Dict with video data matching the project's standard miner format.
    """
    key = api_key or _load_api_key()
    mode = "api"

    if key:
        print(f"Using YouTube Data API v3 for '{query}'...", file=sys.stderr)
        videos = _mine_with_api(query, limit=limit, api_key=key)
    else:
        mode = "rss_fallback"
        print(
            f"No YOUTUBE_API_KEY found — using RSS fallback for '{query}' "
            "(stats unavailable)...",
            file=sys.stderr,
        )
        videos = _mine_with_rss(query, limit=limit)

    return {
        "source": "youtube",
        "query": query,
        "mode": mode,
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "video_count": len(videos),
        "videos": videos,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mine trending YouTube videos (API key optional)",
    )
    parser.add_argument("query", help="Search query (e.g. 'Taylor Swift')")
    parser.add_argument("--limit", type=int, default=15, help="Max videos to return (default: 15)")
    parser.add_argument("--api-key", default=None, help="YouTube API key (overrides .env)")
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON output here")
    args = parser.parse_args()

    result = mine_youtube(args.query, limit=args.limit, api_key=args.api_key)

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
