"""Agent that analyzes scored trend data and identifies sticker opportunities.

This agent is a trend ANALYST, not a trend inventor. It receives a TrendReport
(from miners.trend_scorer) containing verified, data-backed trend signals and
explains what they mean, which have sticker potential, and what to act on.

Usage:
  python -m agents.subtopic_agent "Taylor Swift" --reddit-data output/reddit.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.topic import SubtopicResult
from schemas.trend import TrendReport

load_dotenv()
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """\
You are a trend ANALYST, not a trend inventor. You only work with verified data.
Never claim something is trending without data to support it.

You receive a TrendReport containing quantified trend signals mined from Reddit
and Google Trends. Each signal has hard metrics: post counts, engagement scores,
spike scores, engagement velocity, and links to actual posts as evidence.

Your job is to:
1. Explain what each trend signal means in plain English — what's happening and why people care.
2. Identify which trends have the best STICKER POTENTIAL — visual appeal, quotability,
   emotional resonance, community identity.
3. Add cultural context the numbers can't capture — is this a meme, a moment, a movement?
4. Highlight the most actionable opportunities — what should be designed RIGHT NOW.

For each subtopic you output:
- Reference the actual metrics (spike_score, engagement_velocity, post_count).
- Include evidence URLs from the TrendReport so everything is verifiable.
- Set trending_score based on the data: "hot" = spike_score > 2.0, "warm" = 1.0-2.0, "steady" = below 1.0.

NEVER invent trends. If the data is thin, say so. If a cluster looks noisy, skip it.
Quality over quantity — 3 strong, verified subtopics beats 8 guesses.\
"""


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(DEFAULT_MODEL, provider=provider)


subtopic_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=SubtopicResult,
)


def discover_subtopics(
    topic: str,
    trend_report: TrendReport | dict | None = None,
    reddit_data: dict | None = None,
    trends_data: dict | None = None,
) -> SubtopicResult:
    """Run the subtopic analysis agent on scored trend data.

    Args:
        topic: The cultural topic being explored.
        trend_report: A TrendReport (or its dict form) from trend_scorer.
        reddit_data: Legacy — raw Reddit data (used if trend_report is None).
        trends_data: Legacy — raw Google Trends data (used if trend_report is None).
    """
    parts = [f"Topic: {topic}\n"]

    if trend_report is not None:
        # Convert to dict if it's a Pydantic model
        if isinstance(trend_report, TrendReport):
            report_dict = trend_report.model_dump()
        else:
            report_dict = trend_report

        parts.append(
            "## Scored Trend Report (verified data)\n"
            f"{json.dumps(report_dict, indent=2, ensure_ascii=False)}\n"
        )
        parts.append(
            "Analyze these data-backed trends. For each subtopic you identify, "
            "reference the spike_score, engagement_velocity, and evidence URLs. "
            "Only surface trends that the data supports."
        )
    elif reddit_data or trends_data:
        # Fallback: if caller passes raw data, score it first
        from miners.trend_scorer import score_trends

        report = score_trends(reddit_data or {}, trends_data)
        report_dict = report.model_dump()
        parts.append(
            "## Scored Trend Report (verified data)\n"
            f"{json.dumps(report_dict, indent=2, ensure_ascii=False)}\n"
        )
        parts.append(
            "Analyze these data-backed trends. For each subtopic you identify, "
            "reference the spike_score, engagement_velocity, and evidence URLs."
        )
    else:
        parts.append(
            "No trend data was provided. I cannot identify trends without data. "
            "Please provide Reddit or Google Trends data to analyze."
        )

    user_prompt = "\n".join(parts)
    result = subtopic_agent.run_sync(user_prompt)
    return result.output


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze scored trends for sticker opportunities")
    parser.add_argument("topic", help="Cultural topic to explore (e.g. 'Taylor Swift')")
    parser.add_argument(
        "--reddit-data", type=Path, default=None,
        help="Path to Reddit miner output JSON",
    )
    parser.add_argument(
        "--trends-data", type=Path, default=None,
        help="Path to Google Trends miner output JSON",
    )
    parser.add_argument(
        "--trend-report", type=Path, default=None,
        help="Path to pre-scored TrendReport JSON (preferred)",
    )
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON result here")
    args = parser.parse_args()

    trend_report = None
    if args.trend_report and args.trend_report.exists():
        trend_report = json.loads(args.trend_report.read_text(encoding="utf-8"))

    reddit = None
    if args.reddit_data and args.reddit_data.exists():
        reddit = json.loads(args.reddit_data.read_text(encoding="utf-8"))

    trends = None
    if args.trends_data and args.trends_data.exists():
        trends = json.loads(args.trends_data.read_text(encoding="utf-8"))

    print(f"Analyzing trends for: {args.topic}")
    result = discover_subtopics(
        args.topic,
        trend_report=trend_report,
        reddit_data=reddit,
        trends_data=trends,
    )

    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
