"""Pure-Python trend scorer — NO AI calls.

Takes raw Reddit + Google Trends data and computes verifiable trend metrics.
Groups posts by keyword clustering, calculates engagement velocity, spike scores,
and attaches evidence items so every trend claim is backed by data.

Usage:
  from miners.trend_scorer import score_trends
  report = score_trends(reddit_data, trends_data)
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from miners.sentiment import analyze_sentiment_batch
from miners.spike_detector import score_engagement_spike
from schemas.trend import EvidenceItem, TrendReport, TrendSignal

# Common English stopwords + Reddit noise words — kept minimal on purpose
_STOPWORDS = frozenset(
    "a an the and or but in on at to for of is it its i me my we our you your "
    "he she they them this that with from by as be was were been are am do does "
    "did have has had will would can could should may might not no so if just "
    "about up out all very what which who when where how any than too also into "
    "over after before between each few more most other some such only own same "
    "then there these those through under until while why again here once "
    "really like got get know think go going one two still even new dont im ive "
    "thats whats youre hes shes theyre".split()
)

_MIN_WORD_LEN = 4  # ignore words shorter than this
_GENERIC_TREND_WORDS = frozenset(
    {
        "stage", "technical", "issue", "festival", "performance", "crowd",
        "music", "artist", "lineup", "weekend", "show", "set", "vibe",
    }
)


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip non-alpha, remove stopwords and short words."""
    words = re.findall(r"[a-z]+", text.lower())
    return [w for w in words if len(w) >= _MIN_WORD_LEN and w not in _STOPWORDS]


def _cluster_posts(posts: list[dict]) -> dict[str, list[dict]]:
    """Group posts that share 2+ significant title words.

    Simple but effective: build an inverted index of word -> posts,
    then merge posts that share enough vocabulary.
    """
    # Build token sets per post
    tokenized = []
    for post in posts:
        tokens = set(_tokenize(post.get("title", "")))
        tokenized.append(tokens)

    # Track which cluster each post belongs to (-1 = unassigned)
    assignments = [-1] * len(posts)
    clusters: dict[int, set[int]] = {}  # cluster_id -> set of post indices
    next_id = 0

    for i in range(len(posts)):
        if assignments[i] != -1:
            continue

        # Start a new cluster with this post
        cluster_id = next_id
        next_id += 1
        clusters[cluster_id] = {i}
        assignments[i] = cluster_id

        # Find all unassigned posts sharing 2+ words with any post in this cluster
        # Simple single-pass (good enough for <1000 posts)
        cluster_tokens = set(tokenized[i])
        for j in range(i + 1, len(posts)):
            if assignments[j] != -1:
                continue
            overlap = cluster_tokens & tokenized[j]
            if len(overlap) >= 2:
                clusters[cluster_id].add(j)
                assignments[j] = cluster_id
                cluster_tokens |= tokenized[j]

    # Name each cluster by most common significant words across its posts
    named_clusters: dict[str, list[dict]] = {}
    for cid, indices in clusters.items():
        word_counts: Counter[str] = Counter()
        cluster_posts = []
        for idx in indices:
            cluster_posts.append(posts[idx])
            word_counts.update(_tokenize(posts[idx].get("title", "")))

        # Prefer an event-like title for naming to avoid generic labels.
        top_post = max(cluster_posts, key=lambda p: p.get("score", 0), default={})
        top_title = (top_post.get("title", "") or "").strip()
        title_tokens = [w for w in _tokenize(top_title) if w not in _GENERIC_TREND_WORDS]

        if top_title and len(title_tokens) >= 2:
            words = top_title.split()
            name = " ".join(words[:8]).strip(" -:;,.!?")
        else:
            top_words = [w for w, _ in word_counts.most_common(6) if w not in _GENERIC_TREND_WORDS]
            name = " ".join(top_words[:3]) if top_words else f"cluster_{cid}"
        named_clusters[name] = cluster_posts

    return named_clusters


def _parse_iso(dt_str: str) -> datetime:
    """Parse ISO datetime string, tolerant of various formats."""
    try:
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return datetime.now(tz=timezone.utc)


def _hours_between(earlier: datetime, later: datetime) -> float:
    """Hours between two datetimes. Minimum 0.1 to avoid division by zero."""
    delta = (later - earlier).total_seconds() / 3600
    return max(delta, 0.1)


def _determine_direction(posts: list[dict]) -> str:
    """Compare engagement in first half vs second half of posts (sorted by time)."""
    if len(posts) < 2:
        return "steady"

    sorted_posts = sorted(posts, key=lambda p: p.get("created_utc", ""))
    mid = len(sorted_posts) // 2
    first_half_avg = sum(p.get("score", 0) for p in sorted_posts[:mid]) / max(mid, 1)
    second_half_avg = sum(p.get("score", 0) for p in sorted_posts[mid:]) / max(
        len(sorted_posts) - mid, 1
    )

    ratio = second_half_avg / max(first_half_avg, 1)
    if ratio > 1.5:
        return "rising"
    elif ratio > 1.1:
        return "peaking"
    elif ratio < 0.6:
        return "falling"
    return "steady"


def _match_cluster_to_text(cluster_words: set[str], text: str) -> bool:
    """Check if a cluster name matches a piece of text (case-insensitive, partial)."""
    if not text or not cluster_words:
        return False
    text_words = set(_tokenize(text))
    # At least 1 significant word overlap
    return len(cluster_words & text_words) >= 1


# Platform weights for cross_platform_score
_PLATFORM_WEIGHTS = {
    "reddit": 1.0,
    "google_trends": 1.5,
    "youtube": 1.2,
    "wikipedia": 1.3,
    "web_search": 0.8,
}


def _compute_confidence(
    platform_count: int, spike_score: float, cross_platform_score: float
) -> str:
    """Determine confidence level from cross-platform signals."""
    if platform_count >= 3 and spike_score > 1.5:
        return "high"
    if platform_count >= 2 and spike_score > 1.0:
        return "medium"
    if cross_platform_score > 2.0:
        return "medium"
    return "low"


def score_trends(
    reddit_data: dict | None = None,
    trends_data: dict | None = None,
    youtube_data: dict | None = None,
    wikipedia_data: dict | None = None,
    web_search_data: dict | None = None,
    baseline_score: float = 100.0,
) -> TrendReport:
    """Score and rank trends from all data sources with cross-platform correlation.

    Args:
        reddit_data: Output from mine_multiple_subreddits().
        trends_data: Output from mine_multiple_keywords() (optional).
        youtube_data: Output from mine_youtube() (optional).
        wikipedia_data: Output from search_wikipedia_trends() (optional).
        web_search_data: Output from mine_web_search() (optional).
        baseline_score: Assumed median post score when subreddit median unavailable.

    Returns:
        TrendReport with ranked, evidence-backed, cross-correlated trend signals.
    """
    now = datetime.now(tz=timezone.utc)

    # Handle case where reddit_data is None
    if reddit_data is None:
        reddit_data = {"subreddits": []}

    # Flatten all posts from all subreddits
    all_posts: list[dict] = []
    subreddit_names: set[str] = set()
    for sub_data in reddit_data.get("subreddits", []):
        sub_name = sub_data.get("subreddit", "unknown")
        subreddit_names.add(sub_name)
        for post in sub_data.get("posts", []):
            post["_subreddit"] = sub_name
            all_posts.append(post)

    # Cluster posts by topic
    clusters = _cluster_posts(all_posts)

    # Build Google Trends lookup for matching
    rising_queries: dict[str, dict] = {}  # lowercase query -> data
    if trends_data:
        for kw_data in trends_data.get("keywords", []):
            for rq in kw_data.get("related_queries", {}).get("rising", []):
                query_lower = rq.get("query", "").lower()
                rising_queries[query_lower] = rq

    # Build YouTube lookup: title words -> video data
    yt_videos: list[dict] = []
    if youtube_data:
        yt_videos = youtube_data.get("videos", [])

    # Build Wikipedia lookup: article title -> pageview data
    wiki_articles: list[dict] = []
    if wikipedia_data:
        wiki_articles = wikipedia_data.get("articles", [])

    # Build web search lookup: results list
    web_results: list[dict] = []
    if web_search_data:
        web_results = web_search_data.get("results", [])

    # Score each cluster
    trend_signals: list[TrendSignal] = []

    for cluster_name, posts in clusters.items():
        if not posts:
            continue

        post_count = len(posts)
        total_score = sum(p.get("score", 0) for p in posts)
        total_comments = sum(p.get("num_comments", 0) for p in posts)
        avg_score = total_score / post_count

        # Time calculations
        timestamps = [_parse_iso(p.get("created_utc", "")) for p in posts]
        earliest = min(timestamps)
        latest = max(timestamps)
        hours_span = _hours_between(earliest, now)

        engagement_velocity = total_score / hours_span
        spike_score = avg_score / baseline_score

        # Peak post
        peak_post = max(posts, key=lambda p: p.get("score", 0))
        peak_time = _parse_iso(peak_post.get("created_utc", ""))

        # Direction
        direction = _determine_direction(posts)

        # ── Sentiment analysis (VADER — free, instant) ──────────────
        titles = [p.get("title", "") for p in posts if p.get("title")]
        sentiment_stats = analyze_sentiment_batch(titles)
        sentiment_score = sentiment_stats["avg_compound"]
        emotional_intensity_val = sentiment_stats["emotional_intensity"]
        sentiment_label = (
            "strong_positive" if sentiment_score > 0.5
            else "positive" if sentiment_score > 0.05
            else "neutral" if sentiment_score >= -0.05
            else "negative" if sentiment_score >= -0.5
            else "strong_negative"
        )

        # ── Poisson spike detection (pure math — zero cost) ─────────
        spike_result = score_engagement_spike(posts, time_bucket_hours=6)
        poisson_eta = spike_result["max_eta"]
        spike_magnitude = (
            "extreme" if poisson_eta >= 3.0
            else "notable" if poisson_eta >= 2.0
            else "mild" if poisson_eta >= 1.0
            else "none"
        )

        # Time window description
        if hours_span <= 24:
            time_window = "last 24h"
        elif hours_span <= 168:
            time_window = "last 7d"
        else:
            time_window = f"last {int(hours_span / 24)}d"

        # Build evidence items
        evidence: list[EvidenceItem] = []
        # Add top 5 posts by score as evidence
        top_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)[:5]
        for p in top_posts:
            evidence.append(
                EvidenceItem(
                    source="reddit",
                    url=p.get("url", ""),
                    title=p.get("title", ""),
                    metric_name="score",
                    metric_value=float(p.get("score", 0)),
                    timestamp=p.get("created_utc", now.isoformat()),
                )
            )

        # --- Cross-platform matching ---
        search_interest: int | None = None
        search_interest_change: str | None = None
        platforms_confirmed: list[str] = ["reddit"]
        cluster_words = set(cluster_name.lower().split())

        # Wikipedia correlation
        wikipedia_spike_ratio: float | None = None
        for article in wiki_articles:
            title = article.get("title", "")
            if _match_cluster_to_text(cluster_words, title):
                sr = article.get("spike_ratio", 0.0)
                wikipedia_spike_ratio = sr
                platforms_confirmed.append("wikipedia")
                evidence.append(
                    EvidenceItem(
                        source="wikipedia",
                        url=article.get("url", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"),
                        title=title,
                        metric_name="spike_ratio",
                        metric_value=float(sr),
                        timestamp=now.isoformat(),
                    )
                )
                break

        # YouTube correlation
        youtube_view_velocity: float | None = None
        for video in yt_videos:
            title = video.get("title", "")
            if _match_cluster_to_text(cluster_words, title):
                vph = video.get("views_per_hour")
                if vph is not None:
                    youtube_view_velocity = float(vph)
                platforms_confirmed.append("youtube")
                evidence.append(
                    EvidenceItem(
                        source="youtube",
                        url=video.get("url", ""),
                        title=title,
                        metric_name="views_per_hour",
                        metric_value=float(vph or video.get("view_count", 0)),
                        timestamp=video.get("published_at", now.isoformat()),
                    )
                )
                break

        # Google Trends correlation
        for query_text, query_data in rising_queries.items():
            query_words = set(_tokenize(query_text))
            if len(cluster_words & query_words) >= 1:
                value_str = str(query_data.get("value", ""))
                search_interest_change = value_str
                platforms_confirmed.append("google_trends")
                evidence.append(
                    EvidenceItem(
                        source="google_trends",
                        url=f"https://trends.google.com/trends/explore?q={query_text.replace(' ', '+')}",
                        title=query_text,
                        metric_name="search_interest",
                        metric_value=float(
                            re.sub(r"[^\d.]", "", value_str) or 0
                        ),
                        timestamp=now.isoformat(),
                    )
                )
                break  # one match is enough

        # Web search correlation
        web_mentions: int | None = None
        matching_web = 0
        for result in web_results:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            combined = f"{title} {snippet}"
            if _match_cluster_to_text(cluster_words, combined):
                matching_web += 1
                if matching_web == 1:
                    # Add first match as evidence
                    evidence.append(
                        EvidenceItem(
                            source="web_search",
                            url=result.get("url", ""),
                            title=title,
                            metric_name="web_mention",
                            metric_value=1.0,
                            timestamp=now.isoformat(),
                        )
                    )
        if matching_web > 0:
            web_mentions = matching_web
            platforms_confirmed.append("web_search")

        # Also check interest_over_time from trends data
        if trends_data and search_interest is None:
            for kw_data in trends_data.get("keywords", []):
                iot = kw_data.get("interest_over_time", [])
                if iot:
                    latest_point = iot[-1]
                    search_interest = latest_point.get("interest")

        # Deduplicate platforms
        platforms_confirmed = list(dict.fromkeys(platforms_confirmed))
        platform_count = len(platforms_confirmed)

        # Cross-platform score: weighted sum of confirmed platforms
        cross_platform_score = sum(
            _PLATFORM_WEIGHTS.get(p, 0.5) for p in platforms_confirmed
        )

        # Confidence rating
        confidence = _compute_confidence(platform_count, spike_score, cross_platform_score)

        # Build the description from the top post titles
        desc_posts = top_posts[:3]
        desc = "; ".join(p.get("title", "")[:80] for p in desc_posts)

        trend_signals.append(
            TrendSignal(
                name=cluster_name,
                description=f"Cluster of {post_count} posts: {desc}",
                post_count=post_count,
                total_engagement=total_score,
                avg_engagement_rate=round(avg_score, 1),
                engagement_velocity=round(engagement_velocity, 2),
                spike_score=round(spike_score, 2),
                peak_post_score=peak_post.get("score", 0),
                comment_volume=total_comments,
                time_window=time_window,
                first_seen=earliest.isoformat(),
                peak_time=peak_time.isoformat(),
                trend_direction=direction,
                search_interest=search_interest,
                search_interest_change=search_interest_change,
                platform_count=platform_count,
                cross_platform_score=round(cross_platform_score, 2),
                platforms_confirmed=platforms_confirmed,
                confidence=confidence,
                wikipedia_spike_ratio=wikipedia_spike_ratio,
                youtube_view_velocity=youtube_view_velocity,
                web_mentions=web_mentions,
                sentiment_score=round(sentiment_score, 4),
                emotional_intensity=round(emotional_intensity_val, 4),
                sentiment_label=sentiment_label,
                poisson_eta=round(poisson_eta, 4),
                spike_magnitude=spike_magnitude,
                evidence=evidence,
                source_platforms=platforms_confirmed,
            )
        )

    # Sort by cross_platform_score first, then spike_score
    trend_signals.sort(
        key=lambda t: (t.cross_platform_score, t.spike_score), reverse=True
    )

    return TrendReport(
        query=reddit_data.get("subreddits", [{}])[0].get("subreddit", "unknown")
        if reddit_data.get("subreddits")
        else "unknown",
        analyzed_at=now.isoformat(),
        total_posts_analyzed=len(all_posts),
        total_subreddits_scanned=len(subreddit_names),
        trends=trend_signals,
    )
