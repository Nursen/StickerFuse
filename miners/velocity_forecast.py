"""Forecast whether a trend is accelerating, stable, or fading.

Uses simple linear regression on engagement time series to predict
future trajectory. No ML dependencies -- pure math.

Usage:
  Used internally by trend_scorer, not typically called directly.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Simple least-squares linear regression.

    Returns (slope, intercept, r_squared).
    slope > 0 = accelerating, slope < 0 = fading
    r_squared close to 1 = confident prediction
    """
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, 0.0

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)

    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-10:
        return 0.0, sum_y / n, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R-squared
    y_mean = sum_y / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return slope, intercept, r_squared


def _normalize_data_points(data_points: list[dict]) -> tuple[list[float], list[float]]:
    """Convert varied input formats into (hours_from_start, engagement) lists.

    Supported formats:
      - {"timestamp": ISO str, "engagement": number}
      - {"date": str, "count": number}   (Wikipedia-style)
      - {"hours_ago": number, "score": number}  (Reddit post-style)
    """
    hours: list[float] = []
    values: list[float] = []

    if not data_points:
        return hours, values

    # Detect format from first data point's keys
    sample = data_points[0]

    if "hours_ago" in sample:
        # Reddit-style: hours_ago is relative, convert so earlier = smaller x
        # hours_ago=48 means 48 hours ago (earliest), hours_ago=1 means 1 hour ago (latest)
        for dp in data_points:
            h = float(dp["hours_ago"])
            v = float(dp.get("score", dp.get("engagement", 0)))
            hours.append(-h)  # negate so timeline goes forward
            values.append(v)

    elif "date" in sample:
        # Wikipedia-style: parse date strings, convert to hours from first point
        parsed: list[tuple[datetime, float]] = []
        for dp in data_points:
            dt = _parse_date(dp["date"])
            v = float(dp.get("count", dp.get("views", dp.get("engagement", 0))))
            parsed.append((dt, v))
        parsed.sort(key=lambda p: p[0])
        t0 = parsed[0][0]
        for dt, v in parsed:
            delta = (dt - t0).total_seconds() / 3600.0
            hours.append(delta)
            values.append(v)

    elif "timestamp" in sample:
        # Generic: ISO timestamp + engagement
        parsed_ts: list[tuple[datetime, float]] = []
        for dp in data_points:
            dt = datetime.fromisoformat(dp["timestamp"])
            v = float(dp.get("engagement", dp.get("score", dp.get("count", 0))))
            parsed_ts.append((dt, v))
        parsed_ts.sort(key=lambda p: p[0])
        t0 = parsed_ts[0][0]
        for dt, v in parsed_ts:
            delta = (dt - t0).total_seconds() / 3600.0
            hours.append(delta)
            values.append(v)

    else:
        # Fallback: assume numeric index, one point per hour
        for i, dp in enumerate(data_points):
            hours.append(float(i))
            # Try common value keys
            v = dp.get("engagement", dp.get("score", dp.get("count", dp.get("value", 0))))
            values.append(float(v))

    return hours, values


def _parse_date(date_str: str) -> datetime:
    """Parse a date string in common formats."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Last resort: ISO format
    return datetime.fromisoformat(date_str)


def forecast_trend_velocity(
    data_points: list[dict],
    forecast_hours: int = 72,
) -> dict:
    """Forecast trend trajectory from time-series engagement data.

    Args:
        data_points: List of dicts in one of these formats:
            - {"timestamp": ISO str, "engagement": int/float}
            - {"date": str, "count": int}  (Wikipedia-style)
            - {"hours_ago": float, "score": int}  (Reddit post-style)
        forecast_hours: How far ahead to predict (default 72h = 3 days).

    Returns:
        Dict with slope, r_squared, predictions, trajectory classification,
        and a human-readable summary.
    """
    hours, values = _normalize_data_points(data_points)

    if len(hours) < 2:
        return {
            "slope": 0.0,
            "r_squared": 0.0,
            "current_rate": values[0] if values else 0,
            "predicted_rate_24h": None,
            "predicted_rate_72h": None,
            "trajectory": "insufficient_data",
            "confidence": "low",
            "will_be_trending_in_3_days": None,
            "half_life_hours": None,
            "summary": "Not enough data points to forecast (need at least 2).",
        }

    # Run linear regression
    slope, intercept, r_squared = linear_regression(hours, values)

    # Current rate = last observed value
    current_rate = values[-1]
    max_hour = max(hours)

    # Predictions (clamp to zero -- negative engagement makes no sense)
    predicted_24h = max(0.0, slope * (max_hour + 24) + intercept)
    predicted_72h = max(0.0, slope * (max_hour + forecast_hours) + intercept)

    # Classify trajectory
    if r_squared < 0.3:
        trajectory = "volatile"  # too noisy to predict
    elif current_rate > 0 and slope > current_rate * 0.05:
        trajectory = "accelerating"
    elif current_rate > 0 and slope > -current_rate * 0.05:
        trajectory = "stable"
    elif current_rate > 0 and slope > -current_rate * 0.2:
        trajectory = "decelerating"
    else:
        trajectory = "fading"

    # Half-life: hours until engagement drops to half of current level
    half_life: float | None = None
    if slope < 0 and current_rate > 0:
        half_life = round(-current_rate / (2 * slope), 1)

    # Will it still be trending in 3 days?
    # Threshold: still above 30% of current engagement level
    will_be_trending = predicted_72h > current_rate * 0.3 if current_rate > 0 else None

    # Confidence label from r_squared
    if r_squared > 0.7:
        confidence = "high"
    elif r_squared > 0.4:
        confidence = "medium"
    else:
        confidence = "low"

    # Human-readable summary
    direction = "Growing" if slope > 0 else "Declining"
    summary = (
        f"{direction} at {slope:+.1f} engagement/hour with {confidence} confidence. "
        f"Predicted to {'still be strong' if will_be_trending else 'fade'} in {forecast_hours}h."
    )
    if half_life is not None:
        summary += f" Half-life: {half_life:.0f}h."

    return {
        "slope": round(slope, 4),
        "r_squared": round(r_squared, 4),
        "current_rate": round(current_rate, 2),
        "predicted_rate_24h": round(predicted_24h, 2),
        "predicted_rate_72h": round(predicted_72h, 2),
        "trajectory": trajectory,
        "confidence": confidence,
        "will_be_trending_in_3_days": will_be_trending,
        "half_life_hours": half_life,
        "summary": summary,
    }
