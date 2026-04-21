"""Top-down trend scorer — Google Trends is source of truth, Reddit/YouTube/Wikipedia validate.

Instead of clustering Reddit posts bottom-up (which produces garbage because post titles are
unique), we start with what Google Trends says is actually trending, then look for engagement
evidence across Reddit, YouTube, Wikipedia, and web search.

Usage:
  from miners.trend_scorer import score_trends
  report = score_trends(reddit_data, trends_data, youtube_data, wikipedia_data, web_search_data)
"""
from __future__ import annotations

import re
import sys
from collections import Counter
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


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip non-alpha, remove stopwords and short words."""
    words = re.findall(r"[a-z]+", text.lower())
    return [w for w in words if len(w) >= _MIN_WORD_LEN and w not in _STOPWORDS]


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


# ---------------------------------------------------------------------------
# Top-down trend candidate extraction
# ---------------------------------------------------------------------------


def _extract_trend_candidates(
    trends_data: dict | None,
    youtube_data: dict | None,
    wikipedia_data: dict | None,
) -> list[dict]:
    """Extract trend candidates from all data sources (top-down).

    Google Trends is the primary signal. YouTube viral videos and Wikipedia
    spikes are secondary signals that can also surface trends.
    """
    candidates: list[dict] = []

    # 1. From Google Trends rising queries (strongest signal)
    if trends_data:
        for kw_data in trends_data.get("keywords", []):
            for rq in kw_data.get("related_queries", {}).get("rising", []):
                candidates.append({
                    "name": rq["query"],
                    "source": "google_trends_rising",
                    "search_value": rq.get("value", ""),
                })
            # Top queries give baseline context — take top 5
            for tq in kw_data.get("related_queries", {}).get("top", [])[:5]:
                candidates.append({
                    "name": tq["query"],
                    "source": "google_trends_top",
                    "search_value": tq.get("value", 0),
                })

        # Top trending searches (the "what's trending now" list)
        for topic in trends_data.get("top_trending_searches", []):
            candidates.append({
                "name": topic,
                "source": "google_trending_searches",
                "search_value": "Trending",
            })

    # 2. From YouTube titles (high-engagement videos are trend signals)
    if youtube_data:
        for video in youtube_data.get("videos", []):
            if video.get("view_count", 0) > 10000:
                candidates.append({
                    "name": video["title"][:60],
                    "source": "youtube_viral",
                    "search_value": video.get("view_count", 0),
                })

    # 3. From Wikipedia spikes
    if wikipedia_data:
        for article in wikipedia_data.get("articles", []):
            if article.get("spike_ratio", 0) > 1.3:
                candidates.append({
                    "name": article["title"],
                    "source": "wikipedia_spike",
                    "search_value": article.get("spike_ratio", 0),
                })

    return candidates


def _deduplicate_candidates(candidates: list[dict]) -> list[dict]:
    """Merge candidates whose names share 50%+ significant words.

    Keeps the more specific name (longer token set) and merges sources.
    """
    if not candidates:
        return []

    # Build token sets
    tokenized = [set(_tokenize(c["name"])) for c in candidates]
    merged = [False] * len(candidates)
    result: list[dict] = []

    for i in range(len(candidates)):
        if merged[i]:
            continue

        group = [i]
        group_tokens = set(tokenized[i])

        for j in range(i + 1, len(candidates)):
            if merged[j]:
                continue
            if not tokenized[i] or not tokenized[j]:
                # For very short names, check substring match
                if (candidates[i]["name"].lower() in candidates[j]["name"].lower()
                        or candidates[j]["name"].lower() in candidates[i]["name"].lower()):
                    group.append(j)
                    merged[j] = True
                    group_tokens |= tokenized[j]
                continue

            overlap = tokenized[i] & tokenized[j]
            min_len = min(len(tokenized[i]), len(tokenized[j]))
            if min_len > 0 and len(overlap) / min_len >= 0.5:
                group.append(j)
                merged[j] = True
                group_tokens |= tokenized[j]

        # Pick the most specific name (longest token set)
        best_idx = max(group, key=lambda idx: len(tokenized[idx]))
        best = dict(candidates[best_idx])

        # Collect all sources
        all_sources = [candidates[idx]["source"] for idx in group]
        best["merged_sources"] = list(dict.fromkeys(all_sources))

        # Keep the strongest search_value
        for idx in group:
            sv = candidates[idx]["search_value"]
            if sv == "Breakout" or sv == "Trending":
                best["search_value"] = sv
                break

        result.append(best)
        merged[i] = True

    return result


# ---------------------------------------------------------------------------
# Validation: match trend candidates to platform evidence
# ---------------------------------------------------------------------------


def _find_matching_posts(trend_name: str, posts: list[dict]) -> list[dict]:
    """Find Reddit posts whose titles are relevant to this trend."""
    trend_words = set(_tokenize(trend_name))
    if not trend_words:
        # Fall back to substring match for short trend names
        matching = []
        for post in posts:
            if trend_name.lower() in post.get("title", "").lower():
                matching.append(post)
        return matching

    matching = []
    for post in posts:
        post_words = set(_tokenize(post.get("title", "")))
        # Need significant word overlap OR full trend name as substring
        threshold = max(1, len(trend_words) // 2)
        if len(trend_words & post_words) >= threshold:
            matching.append(post)
        elif trend_name.lower() in post.get("title", "").lower():
            matching.append(post)
    return matching


def _find_matching_videos(trend_name: str, videos: list[dict]) -> list[dict]:
    """Find YouTube videos whose titles match this trend."""
    trend_words = set(_tokenize(trend_name))
    matching = []
    for video in videos:
        title = video.get("title", "")
        if not trend_words:
            if trend_name.lower() in title.lower():
                matching.append(video)
            continue
        video_words = set(_tokenize(title))
        if len(trend_words & video_words) >= max(1, len(trend_words) // 2):
            matching.append(video)
        elif trend_name.lower() in title.lower():
            matching.append(video)
    return matching


def _find_matching_wiki(trend_name: str, articles: list[dict]) -> list[dict]:
    """Find Wikipedia articles matching this trend."""
    trend_words = set(_tokenize(trend_name))
    matching = []
    for article in articles:
        title = article.get("title", "")
        if not trend_words:
            if trend_name.lower() in title.lower():
                matching.append(article)
            continue
        article_words = set(_tokenize(title))
        if len(trend_words & article_words) >= 1:
            matching.append(article)
        elif trend_name.lower() in title.lower():
            matching.append(article)
    return matching


def _find_matching_web(trend_name: str, results: list[dict]) -> list[dict]:
    """Find web search results matching this trend."""
    trend_words = set(_tokenize(trend_name))
    matching = []
    for result in results:
        combined = f"{result.get('title', '')} {result.get('snippet', '')}"
        if not trend_words:
            if trend_name.lower() in combined.lower():
                matching.append(result)
            continue
        combined_words = set(_tokenize(combined))
        if len(trend_words & combined_words) >= 1:
            matching.append(result)
        elif trend_name.lower() in combined.lower():
            matching.append(result)
    return matching


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def score_trends(
    reddit_data: dict | None = None,
    trends_data: dict | None = None,
    youtube_data: dict | None = None,
    wikipedia_data: dict | None = None,
    web_search_data: dict | None = None,
    baseline_score: float = 100.0,
    min_posts_per_trend: int = 2,
) -> TrendReport:
    """Score and rank trends using a top-down approach.

    Step 1: Google Trends / YouTube / Wikipedia tell us WHAT is trending.
    Step 2: For each trend candidate, search Reddit/YouTube/Wikipedia/web for validation.
    Step 3: Score by search volume spike + cross-platform engagement evidence.
    Step 4: Filter to trends confirmed on 2+ platforms or with "Breakout" status.

    Args:
        reddit_data: Output from mine_multiple_subreddits().
        trends_data: Output from mine_multiple_keywords() (optional).
        youtube_data: Output from mine_youtube() (optional).
        wikipedia_data: Output from search_wikipedia_trends() (optional).
        web_search_data: Output from mine_web_search() (optional).
        baseline_score: Assumed median post score when subreddit median unavailable.
        min_posts_per_trend: Minimum matching Reddit posts (only enforced when Reddit is sole signal).

    Returns:
        TrendReport with ranked, evidence-backed, cross-correlated trend signals.
    """
    now = datetime.now(tz=timezone.utc)

    # Handle None inputs
    if reddit_data is None:
        reddit_data = {"subreddits": []}

    # Flatten all Reddit posts
    all_posts: list[dict] = []
    subreddit_names: set[str] = set()
    for sub_data in reddit_data.get("subreddits", []):
        sub_name = sub_data.get("subreddit", "unknown")
        subreddit_names.add(sub_name)
        for post in sub_data.get("posts", []):
            post["_subreddit"] = sub_name
            all_posts.append(post)

    # Collect platform data
    yt_videos: list[dict] = youtube_data.get("videos", []) if youtube_data else []
    wiki_articles: list[dict] = wikipedia_data.get("articles", []) if wikipedia_data else []
    web_results: list[dict] = web_search_data.get("results", []) if web_search_data else []

    # ── Step 1: Extract trend candidates (top-down) ──────────────────────
    candidates = _extract_trend_candidates(trends_data, youtube_data, wikipedia_data)

    # ── Step 2: Deduplicate candidates ───────────────────────────────────
    candidates = _deduplicate_candidates(candidates)

    # ── Step 3: Validate each candidate and score ────────────────────────
    trend_signals: list[TrendSignal] = []

    for candidate in candidates:
        trend_name = candidate["name"]
        search_value_raw = candidate.get("search_value", "")
        candidate_source = candidate.get("source", "")

        # -- Cross-platform validation --
        platforms_confirmed: list[str] = []
        evidence: list[EvidenceItem] = []

        # Google Trends is confirmed if candidate came from there
        search_volume_signal: str | None = None
        search_interest: int | None = None
        search_interest_change: str | None = None

        if candidate_source.startswith("google_trend"):
            platforms_confirmed.append("google_trends")
            search_volume_signal = str(search_value_raw)
            search_interest_change = str(search_value_raw)

            # Try to parse numeric interest value
            numeric_val = re.sub(r"[^\d.]", "", str(search_value_raw))
            evidence.append(
                EvidenceItem(
                    source="google_trends",
                    url=f"https://trends.google.com/trends/explore?q={trend_name.replace(' ', '+')}",
                    title=trend_name,
                    metric_name="search_interest",
                    metric_value=float(numeric_val) if numeric_val else 0.0,
                    timestamp=now.isoformat(),
                )
            )

        # Also check interest_over_time from trends data for search_interest
        if trends_data and search_interest is None:
            for kw_data in trends_data.get("keywords", []):
                iot = kw_data.get("interest_over_time", [])
                if iot:
                    search_interest = iot[-1].get("interest")

        # -- Reddit validation --
        matching_posts = _find_matching_posts(trend_name, all_posts)
        reddit_match_count = len(matching_posts)

        if matching_posts:
            platforms_confirmed.append("reddit")
            top_posts = sorted(matching_posts, key=lambda p: p.get("score", 0), reverse=True)[:5]
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

        # -- YouTube validation --
        matching_videos = _find_matching_videos(trend_name, yt_videos)
        youtube_match_views = sum(v.get("view_count", 0) for v in matching_videos)
        youtube_view_velocity: float | None = None

        if matching_videos:
            if "youtube" not in platforms_confirmed:
                platforms_confirmed.append("youtube")
            best_video = max(matching_videos, key=lambda v: v.get("view_count", 0))
            youtube_view_velocity = float(best_video.get("views_per_hour", 0) or 0)
            for v in matching_videos[:3]:
                evidence.append(
                    EvidenceItem(
                        source="youtube",
                        url=v.get("url", ""),
                        title=v.get("title", ""),
                        metric_name="view_count",
                        metric_value=float(v.get("view_count", 0)),
                        timestamp=v.get("published_at", now.isoformat()),
                    )
                )

        # -- Wikipedia validation --
        matching_wiki = _find_matching_wiki(trend_name, wiki_articles)
        wikipedia_spike_ratio: float | None = None

        if matching_wiki:
            if "wikipedia" not in platforms_confirmed:
                platforms_confirmed.append("wikipedia")
            best_wiki = max(matching_wiki, key=lambda a: a.get("spike_ratio", 0))
            wikipedia_spike_ratio = best_wiki.get("spike_ratio", 0.0)
            title = best_wiki.get("title", "")
            evidence.append(
                EvidenceItem(
                    source="wikipedia",
                    url=best_wiki.get("url", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"),
                    title=title,
                    metric_name="spike_ratio",
                    metric_value=float(wikipedia_spike_ratio or 0),
                    timestamp=now.isoformat(),
                )
            )

        # -- Web search validation --
        matching_web = _find_matching_web(trend_name, web_results)
        web_mentions: int | None = None

        if matching_web:
            platforms_confirmed.append("web_search")
            web_mentions = len(matching_web)
            first_web = matching_web[0]
            evidence.append(
                EvidenceItem(
                    source="web_search",
                    url=first_web.get("url", ""),
                    title=first_web.get("title", ""),
                    metric_name="web_mention",
                    metric_value=float(len(matching_web)),
                    timestamp=now.isoformat(),
                )
            )

        # -- Filter: need 2+ platforms OR "Breakout"/"Trending" status --
        is_breakout = str(search_value_raw) in ("Breakout", "Trending")
        platform_count = len(dict.fromkeys(platforms_confirmed))
        if platform_count < 2 and not is_breakout:
            continue

        # -- Compute Reddit-based metrics (if matching posts exist) --
        posts = matching_posts if matching_posts else []
        post_count = len(posts)
        total_score = sum(p.get("score", 0) for p in posts)
        total_comments = sum(p.get("num_comments", 0) for p in posts)
        avg_score = total_score / max(post_count, 1)

        # Time calculations from Reddit posts
        if posts:
            timestamps = [_parse_iso(p.get("created_utc", "")) for p in posts]
            earliest = min(timestamps)
            latest = max(timestamps)
            hours_span = _hours_between(earliest, now)
            peak_post = max(posts, key=lambda p: p.get("score", 0))
            peak_time = _parse_iso(peak_post.get("created_utc", ""))
            peak_post_score = peak_post.get("score", 0)
            direction = _determine_direction(posts)
        else:
            earliest = now
            hours_span = 1.0
            peak_time = now
            peak_post_score = 0
            direction = "steady"

        engagement_velocity = total_score / hours_span if hours_span > 0 else 0.0
        spike_score = avg_score / baseline_score if baseline_score > 0 else 0.0

        # ── Sentiment analysis (VADER — free, instant) ──────────────
        if posts:
            titles = [p.get("title", "") for p in posts if p.get("title")]
            sentiment_stats = analyze_sentiment_batch(titles)
            sentiment_score = sentiment_stats["avg_compound"]
            emotional_intensity_val = sentiment_stats["emotional_intensity"]
        else:
            sentiment_score = 0.0
            emotional_intensity_val = 0.0

        sentiment_label = (
            "strong_positive" if sentiment_score > 0.5
            else "positive" if sentiment_score > 0.05
            else "neutral" if sentiment_score >= -0.05
            else "negative" if sentiment_score >= -0.5
            else "strong_negative"
        )

        # ── Poisson spike detection (pure math — zero cost) ─────────
        if posts:
            spike_result = score_engagement_spike(posts, time_bucket_hours=6)
            poisson_eta = spike_result["max_eta"]
        else:
            poisson_eta = 0.0

        spike_magnitude = (
            "extreme" if poisson_eta >= 3.0
            else "notable" if poisson_eta >= 2.0
            else "mild" if poisson_eta >= 1.0
            else "none"
        )

        # Time window
        if hours_span <= 24:
            time_window = "last 24h"
        elif hours_span <= 168:
            time_window = "last 7d"
        else:
            time_window = f"last {int(hours_span / 24)}d"

        # Deduplicate platforms
        platforms_confirmed = list(dict.fromkeys(platforms_confirmed))
        platform_count = len(platforms_confirmed)

        # Cross-platform score: weighted sum of confirmed platforms
        cross_platform_score = sum(
            _PLATFORM_WEIGHTS.get(p, 0.5) for p in platforms_confirmed
        )

        # ── Composite score: weighted combination of all signals ────
        # Normalize search value to 0-1 range
        sv_numeric = 0.0
        sv_str = str(search_value_raw)
        if sv_str == "Breakout":
            sv_numeric = 1.0
        elif sv_str == "Trending":
            sv_numeric = 0.8
        else:
            cleaned = re.sub(r"[^\d.]", "", sv_str)
            if cleaned:
                sv_numeric = min(float(cleaned) / 500.0, 1.0)  # 500% is max expected

        reddit_signal = min(total_score / 5000.0, 1.0) if total_score > 0 else 0.0
        yt_signal = min(youtube_match_views / 1_000_000.0, 1.0) if youtube_match_views > 0 else 0.0
        wiki_signal = min((wikipedia_spike_ratio or 0) / 5.0, 1.0)
        web_signal = min((web_mentions or 0) / 10.0, 1.0)

        composite_score = (
            sv_numeric * 0.35
            + reddit_signal * 0.25
            + yt_signal * 0.20
            + wiki_signal * 0.10
            + web_signal * 0.10
        )

        # Confidence rating
        confidence = _compute_confidence(platform_count, spike_score, cross_platform_score)

        # Build description
        desc_parts = [f"Trending ({candidate_source.replace('_', ' ')})"]
        if reddit_match_count > 0:
            desc_parts.append(f"{reddit_match_count} Reddit posts")
        if youtube_match_views > 0:
            desc_parts.append(f"{youtube_match_views:,} YouTube views")
        if wikipedia_spike_ratio and wikipedia_spike_ratio > 1.0:
            desc_parts.append(f"{wikipedia_spike_ratio:.1f}x Wikipedia spike")
        description = " | ".join(desc_parts)

        trend_signals.append(
            TrendSignal(
                name=trend_name,
                description=description,
                post_count=post_count,
                total_engagement=total_score,
                avg_engagement_rate=round(avg_score, 1),
                engagement_velocity=round(engagement_velocity, 2),
                spike_score=round(spike_score, 2),
                peak_post_score=peak_post_score,
                comment_volume=total_comments,
                time_window=time_window,
                first_seen=earliest.isoformat(),
                peak_time=peak_time.isoformat(),
                trend_direction=direction,
                search_interest=search_interest,
                search_interest_change=search_interest_change,
                search_volume_signal=str(search_value_raw) if search_value_raw else None,
                reddit_match_count=reddit_match_count,
                youtube_match_views=youtube_match_views if youtube_match_views > 0 else None,
                composite_score=round(composite_score, 4),
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

    # Sort by composite_score first, then cross_platform_score
    trend_signals.sort(
        key=lambda t: (t.composite_score or 0, t.cross_platform_score), reverse=True
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
