"""Agent that interprets community mining results and identifies sticker opportunities.

Takes structured data from community_miner (recurring phrases, sentiment, emoji patterns)
and adds cultural interpretation: what are the in-jokes? What would this community
actually buy as stickers? What's the inside meaning?

Uses Gemini Flash-Lite (cheap) since this is creative analysis, not precision work.

Usage:
  from agents.community_agent import analyze_community_text
  analysis = analyze_community_text(mined_data)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.community import CommunityAnalysis

load_dotenv()

# Flash-Lite: cheapest option for creative/interpretive work
COMMUNITY_MODEL = "gemini-2.5-flash-lite"

SYSTEM_PROMPT = """\
You are a community culture analyst specializing in internet communities and \
print-on-demand sticker design.

You receive data mined from community text (chat logs, Discord servers, forum threads) \
containing recurring phrases, sentiment scores, emoji patterns, and usage frequency.

Your job is to:
1. Interpret what the recurring phrases MEAN in context — are they in-jokes, \
   catchphrases, memes, shared references, or identity markers?
2. Assess STICKER POTENTIAL — would someone in this community actually buy a sticker \
   with this phrase? A good sticker phrase is: short, punchy, identity-signaling, \
   and funny/relatable to insiders.
3. Suggest an ART STYLE that matches each phrase's vibe — retro pixel art for gamers, \
   hand-lettered for wholesome communities, bold typography for hype culture, etc.
4. Identify the TARGET AUDIENCE — who are these people? What do they care about?
5. Recommend a STICKER PACK — the top 3-5 phrases that work together as a themed set.

Rules:
- If the data is thin (few recurring phrases, low counts), say so honestly.
- Prioritize phrases with high sticker_score (frequency * emotional intensity).
- A phrase with count=3 and strong sentiment beats count=10 with neutral sentiment.
- Community-specific slang and in-jokes are GOLD — they signal insider identity.
- Generic phrases ("that's so funny") are TRASH — anyone could say that.\
"""


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(COMMUNITY_MODEL, provider=provider)


community_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=CommunityAnalysis,
)


def analyze_community_text(mined_data: dict) -> CommunityAnalysis:
    """Run the community analysis agent on mined community data.

    Args:
        mined_data: Output dict from miners.community_miner.mine_community_text().

    Returns:
        CommunityAnalysis with cultural interpretation and sticker recommendations.
    """
    if "error" in mined_data:
        return CommunityAnalysis(
            community_vibe="Unable to analyze — no messages were extracted.",
            insights=[],
            recommended_sticker_pack=[],
        )

    prompt_parts = [
        "## Community Mining Results\n",
        f"**Stats:** {json.dumps(mined_data.get('community_stats', {}))}\n",
        "**Recurring Phrases (sorted by sticker score):**\n",
    ]

    for phrase_data in mined_data.get("recurring_phrases", []):
        prompt_parts.append(
            f"- \"{phrase_data['phrase']}\" (count={phrase_data['count']}, "
            f"sentiment={phrase_data['sentiment_label']}, "
            f"sticker_score={phrase_data['sticker_score']})\n"
            f"  Example: \"{phrase_data.get('example_context', '')}\"\n"
        )

    emoji_data = mined_data.get("emoji_patterns", [])
    if emoji_data:
        prompt_parts.append("\n**Emoji Patterns:**\n")
        for e in emoji_data:
            prompt_parts.append(f"- {e['emoji']} (used {e['count']} times)\n")

    prompt_parts.append(
        "\nAnalyze these community patterns. For each recurring phrase, "
        "interpret its cultural meaning, assess sticker potential, and suggest "
        "an art style. Then recommend the best 3-5 phrases for a themed sticker pack."
    )

    user_prompt = "".join(prompt_parts)
    result = community_agent.run_sync(user_prompt)
    return result.output
