"""Agent that discovers trending subtopics for a given cultural topic.

Uses Gemini via PydanticAI to analyze raw trend data from Reddit and Google Trends,
then surfaces timely subtopics worth making stickers about.

Usage:
  python -m agents.subtopic_agent "Taylor Swift"
  python -m agents.subtopic_agent "NBA" --reddit-data miners/output/reddit_nba.json
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

load_dotenv()
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """\
You are a trend analyst specializing in viral internet culture and merchandise opportunities.

Given a cultural topic and raw data from social media platforms (Reddit posts, Google Trends data),
your job is to identify the most timely and monetizable SUBTOPICS — specific moments, events,
phrases, or memes that are actively trending right now.

Focus on subtopics that would make great sticker designs:
- Specific quotes, catchphrases, or lyrics people are repeating
- Visual memes or aesthetic movements
- Recent events generating strong emotional reactions
- Niche community in-jokes that fans would buy merch for

Order subtopics by how actively they are trending (hot > warm > steady).
Be specific — "Travis Kelce engagement rumors" is better than "Taylor Swift relationships".
Ground every subtopic in the actual data provided.\
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
    reddit_data: dict | None = None,
    trends_data: dict | None = None,
) -> SubtopicResult:
    """Run the subtopic discovery agent with optional raw platform data."""
    parts = [f"Topic: {topic}\n"]

    if reddit_data:
        parts.append(
            "Reddit data (hot posts from relevant subreddits):\n"
            f"{json.dumps(reddit_data, indent=2, ensure_ascii=False)}\n"
        )

    if trends_data:
        parts.append(
            "Google Trends data (rising search queries):\n"
            f"{json.dumps(trends_data, indent=2, ensure_ascii=False)}\n"
        )

    if not reddit_data and not trends_data:
        parts.append(
            "No raw platform data provided. Use your knowledge of current internet culture "
            "to identify trending subtopics. Note which ones you're most confident about.\n"
        )

    parts.append(
        "Identify 5-8 trending subtopics for this topic that would make great sticker designs."
    )

    user_prompt = "\n".join(parts)
    result = subtopic_agent.run_sync(user_prompt)
    return result.output


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover trending subtopics for a cultural topic")
    parser.add_argument("topic", help="Cultural topic to explore (e.g. 'Taylor Swift')")
    parser.add_argument(
        "--reddit-data", type=Path, default=None,
        help="Path to Reddit miner output JSON",
    )
    parser.add_argument(
        "--trends-data", type=Path, default=None,
        help="Path to Google Trends miner output JSON",
    )
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON result here")
    args = parser.parse_args()

    reddit = None
    if args.reddit_data and args.reddit_data.exists():
        reddit = json.loads(args.reddit_data.read_text(encoding="utf-8"))

    trends = None
    if args.trends_data and args.trends_data.exists():
        trends = json.loads(args.trends_data.read_text(encoding="utf-8"))

    print(f"Discovering subtopics for: {args.topic}")
    result = discover_subtopics(args.topic, reddit_data=reddit, trends_data=trends)

    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
