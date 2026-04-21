"""AI agent that reads Reddit post titles and comments to identify specific viral moments.

Instead of clustering by keywords, this agent understands cultural context — it knows
that "the bath scene", "Benedict saving Sophie", and "the 360 dance" are specific
sticker-worthy moments, not generic topic words.

Uses Gemini Flash (not Lite — needs real comprehension for this task).

CLI:
  python -m agents.moment_detector "Bridgerton" --reddit-data output/reddit.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class ViralMoment(BaseModel):
    """A specific viral moment identified from community conversation."""
    name: str = Field(description="Short name for this moment (e.g. 'The Bath Scene', 'Charlie XCX 360 Dance')")
    description: str = Field(description="What this moment is and why people care about it")
    why_its_viral: str = Field(description="What emotion drives the buzz — nostalgia, humor, outrage, obsession?")
    sticker_potential: str = Field(description="Why this would/wouldn't make a good sticker. HIGH/MEDIUM/LOW.")
    sample_quotes: list[str] = Field(description="2-3 actual quotes from the comments that capture the vibe")
    estimated_buzz: str = Field(description="Based on comment upvotes and frequency: HOT / WARM / NICHE")
    evidence: list[str] = Field(description="Post titles and comment excerpts that reference this moment")


class MomentReport(BaseModel):
    """All viral moments identified from community conversation."""
    topic: str = Field(description="The parent topic analyzed")
    total_posts_analyzed: int
    total_comments_analyzed: int
    moments: list[ViralMoment] = Field(description="Identified viral moments, ordered by buzz level")
    community_vibe: str = Field(description="Overall mood of the community right now (e.g. 'excited about S4', 'nostalgic for S1')")


SYSTEM_PROMPT = """\
You are an expert cultural analyst who identifies specific VIRAL MOMENTS from online community conversations.

You receive Reddit post titles and their top-voted comments about a topic. Your job is to identify
the specific scenes, quotes, memes, cultural references, and emotional flashpoints that the
community is actively buzzing about.

CRITICAL: You are looking for SPECIFIC MOMENTS, not broad topics. Examples:
- GOOD: "The Charlie XCX 360 dance scene in the ballroom" — specific, visual, sticker-worthy
- GOOD: "Benedict and Sophie's bath scene" — specific scene people are obsessed with
- GOOD: "'I wish men were real' as a reaction to the show" — specific quote going viral
- BAD: "Bridgerton Season 4" — too broad, not a moment
- BAD: "The cast" — too generic
- BAD: "Character development" — too abstract

For each moment you identify:
1. What specifically is it? (a scene, a quote, a meme, a cultural crossover)
2. Why are people buzzing about it? (the emotion driving engagement)
3. What would a sticker of this look like? (is it visual? quotable? both?)
4. Quote actual comments that reference it (proof it's real)

Look for:
- Scenes/moments people keep referencing across multiple posts
- Quotes people are repeating or riffing on
- Memes or jokes the community has created
- Emotional flashpoints (things that make people angry, ecstatic, nostalgic)
- Cultural crossovers (brand parodies, other media references)
- Character moments that trigger strong reactions

Rank by ACTUAL ENGAGEMENT (comment upvotes, frequency of mentions) not your own opinion.
If something has 200 upvotes discussing it, that's hotter than something with 5.\
"""


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(DEFAULT_MODEL, provider=provider)


moment_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=MomentReport,
)


def detect_viral_moments(
    topic: str,
    reddit_data: dict,
) -> MomentReport:
    """Analyze Reddit posts + comments to find specific viral moments.

    Args:
        topic: The parent topic (e.g. "Bridgerton")
        reddit_data: Output from mine_multiple_subreddits(include_comments=True)
    """
    # Build a rich context from posts + comments
    parts = [f"Topic: {topic}\n"]

    total_posts = 0
    total_comments = 0

    for sub_data in reddit_data.get("subreddits", []):
        sub_name = sub_data.get("subreddit", "unknown")
        parts.append(f"\n## r/{sub_name}\n")

        for post in sub_data.get("posts", []):
            total_posts += 1
            score = post.get("score", 0)
            title = post.get("title", "")
            selftext = post.get("selftext_preview", "")

            parts.append(f"\n### [{score} upvotes] {title}")
            if selftext:
                parts.append(f"Post body: {selftext[:200]}")

            # Include comments if available
            comments = post.get("top_comments", [])
            if comments:
                parts.append("Top comments:")
                for c in comments:
                    total_comments += 1
                    c_score = c.get("score", 0)
                    c_body = c.get("body", "")[:200]
                    parts.append(f"  [{c_score} upvotes] {c_body}")

    parts.append(f"\n\nAnalyze these {total_posts} posts and {total_comments} comments. "
                 f"Identify the 5-8 most specific viral moments, scenes, quotes, or memes "
                 f"that this community is buzzing about. Every moment must be backed by "
                 f"actual comment evidence.")

    from utils.llm_retry import sync_retry_llm
    result = sync_retry_llm(lambda: moment_agent.run_sync("\n".join(parts)))
    return result.output


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect viral moments from Reddit data using Gemini")
    parser.add_argument("topic", help="Topic name (e.g. 'Bridgerton')")
    parser.add_argument("--reddit-data", type=Path, required=True, help="Path to Reddit JSON (output of reddit_miner)")
    parser.add_argument("-o", "--out", type=Path, default=None, help="Write JSON output here")
    args = parser.parse_args()

    reddit_data = json.loads(args.reddit_data.read_text(encoding="utf-8"))
    report = detect_viral_moments(args.topic, reddit_data)

    text = json.dumps(report.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
