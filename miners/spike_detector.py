"""Poisson-based statistical spike detection — pure math, zero API calls.

Based on Twitter/Gnip Trend Detection: instead of "is this above average?",
we ask "is this count so statistically unlikely under normal conditions that
it must be a real signal?"

The key metric is eta = (observed - expected) / sqrt(expected), a z-score
for count data.  When eta exceeds a threshold, it's trending.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone


def poisson_spike_score(observed: int, expected: float) -> float:
    """Calculate how statistically unusual this count is.

    Uses the Poisson-based eta metric from Twitter's Gnip trend detection.
    eta = (observed - expected) / sqrt(expected)

    Returns eta:
        < 1.0  = normal variation
        1.0-2.0 = mildly unusual
        2.0-3.0 = notably unusual (likely trending)
        > 3.0  = highly unusual (definitely trending)
    """
    if expected <= 0:
        # No baseline — any observation is infinitely unusual,
        # but return a capped value to stay useful downstream.
        return float(observed) if observed > 0 else 0.0
    return (observed - expected) / math.sqrt(expected)


def _spike_magnitude(eta: float) -> str:
    """Human-readable label for a spike eta value."""
    if eta >= 3.0:
        return "extreme"
    if eta >= 2.0:
        return "notable"
    if eta >= 1.0:
        return "mild"
    return "none"


def detect_spikes_in_timeseries(
    counts: list[dict],
    baseline_window: int = 14,
) -> list[dict]:
    """Detect spikes in a time series using the Poisson model.

    Args:
        counts: List of {"date": "2026-04-15", "count": 150} dicts,
                sorted chronologically.
        baseline_window: Number of preceding data points to use for the
                         rolling baseline average.

    Returns a list with the same dates, enriched with eta and spike info.
    """
    results: list[dict] = []

    for i, point in enumerate(counts):
        date = point["date"]
        observed = point["count"]

        # Rolling baseline from the preceding `baseline_window` points
        start = max(0, i - baseline_window)
        window = counts[start:i]  # excludes current point

        if window:
            baseline = sum(p["count"] for p in window) / len(window)
        else:
            # Not enough history — use the observed value as its own baseline
            baseline = float(observed)

        eta = poisson_spike_score(observed, baseline)

        results.append(
            {
                "date": date,
                "count": observed,
                "baseline": round(baseline, 2),
                "eta": round(eta, 4),
                "is_spike": eta >= 2.0,
                "spike_magnitude": _spike_magnitude(eta),
            }
        )

    return results


def _parse_dt(value: str | datetime) -> datetime:
    """Flexibly parse a datetime from string or passthrough."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(tz=timezone.utc)


def _bucket_key(dt: datetime, bucket_hours: int) -> str:
    """Round a datetime down to the start of its time bucket."""
    # Truncate to the nearest bucket_hours boundary
    hour = (dt.hour // bucket_hours) * bucket_hours
    truncated = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    return truncated.isoformat()


def score_engagement_spike(
    posts: list[dict],
    time_bucket_hours: int = 6,
) -> dict:
    """Bucket posts by time period, compute Poisson spike scores per bucket.

    Works with Reddit/YouTube-style data — buckets posts into N-hour windows,
    counts posts and total engagement per window, and detects which windows
    are spiking.

    Each post should have a 'created_utc' (ISO string or datetime) field.

    Returns summary dict with buckets, max_eta, spike info, and baseline rate.
    """
    if not posts:
        return {
            "buckets": [],
            "max_eta": 0.0,
            "spike_detected": False,
            "spike_window": None,
            "baseline_rate": 0.0,
            "spike_rate": 0,
        }

    # Bucket posts
    bucket_counts: dict[str, int] = defaultdict(int)
    for post in posts:
        dt = _parse_dt(post.get("created_utc", ""))
        key = _bucket_key(dt, time_bucket_hours)
        bucket_counts[key] += 1

    # Sort buckets chronologically
    sorted_keys = sorted(bucket_counts.keys())
    timeseries = [{"date": k, "count": bucket_counts[k]} for k in sorted_keys]

    # Run spike detection on the bucketed timeseries
    spike_results = detect_spikes_in_timeseries(timeseries, baseline_window=max(len(timeseries) - 1, 1))

    # Find the peak
    if spike_results:
        peak = max(spike_results, key=lambda r: r["eta"])
        baseline_rate = sum(r["count"] for r in spike_results) / len(spike_results)
    else:
        peak = {"eta": 0.0, "date": None, "count": 0}
        baseline_rate = 0.0

    return {
        "buckets": spike_results,
        "max_eta": peak["eta"],
        "spike_detected": peak["eta"] >= 2.0,
        "spike_window": peak["date"],
        "baseline_rate": round(baseline_rate, 2),
        "spike_rate": peak["count"],
    }
