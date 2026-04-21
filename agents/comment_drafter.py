"""Comment drafter agent -- crafts authentic-sounding comments that naturally mention sticker products.

The golden rule: if it sounds like an ad, it fails. Every comment should read like it was
written by a genuine fan who happens to have spotted a great sticker. The agent reads the
thread vibe first, then matches the community's exact slang, energy, and formatting.

Generates 3 options per thread:
  1. Direct link drop (for high-intent threads)
  2. Subtle reference (for engagement-first threads)
  3. Pure engagement / no mention (builds credibility for the account)

Usage:
  python -m agents.comment_drafter "I burn for you" "https://redbubble.com/..." --thread "What Bridgerton quote lives rent-free in your head?"
  python -m agents.comment_drafter "let him cook bee" "https://redbubble.com/..." --thread-file thread.txt --platform reddit
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Gemini Flash -- needs good comprehension to read thread tone
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CommentDraft(BaseModel):
    comment_text: str = Field(description="The comment to post -- reads like a real fan, not marketing")
    tone: str = Field(description="Tone detected in the thread: playful, sincere, ironic, heated, etc.")
    sticker_mention_style: Literal["link_drop", "subtle_reference", "enthusiastic_share", "no_mention"] = Field(
        description="How the sticker is referenced in the comment"
    )
    platform: Literal["reddit", "youtube", "tiktok"]
    confidence: float = Field(description="How natural does this feel? 0.0-1.0")
    reasoning: str = Field(description="Why this approach works for this specific thread")


class CommentDraftSet(BaseModel):
    thread_url: str
    thread_summary: str = Field(description="Brief summary of what the thread is about")
    thread_tone: str = Field(description="Overall vibe of the thread")
    drafts: list[CommentDraft] = Field(description="3 comment options with different approaches")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a social media native who participates in online communities. You've been asked \
to draft comments for threads where a sticker product could be naturally mentioned.

## THE GOLDEN RULE

If anyone reading your comment would think "this is an ad," you have FAILED. \
The comment must read like it came from a genuine community member who happens to \
know about a relevant sticker.

## HOW TO APPROACH EACH THREAD

1. **Read the room.** What's the thread about? What's the vibe -- playful banter, \
   sincere discussion, ironic shitposting, heated debate? Match it EXACTLY.
2. **Mirror the language.** If the community uses "ngl," "fr fr," "lowkey," or formal \
   complete sentences -- you do too. If they use all-caps for emphasis, you can too. \
   Copy the formatting (short paragraphs on Reddit, single lines on YouTube).
3. **Find the natural entry point.** Your comment should respond to something specific \
   in the thread. Don't just drop a generic "great post!" -- reference a detail.
4. **The sticker mention must feel accidental.** Like you just remembered it exists. \
   Not like you came here to share it.

## BANNED PHRASES (instant fail)

- "check out"
- "available now"
- "link in bio"
- "just launched"
- "use code"
- "I just found this amazing..."
- "Not sponsored but..."
- Any call-to-action language

## GOOD STICKER MENTION PATTERNS

- "ngl I need this on my laptop"
- "someone made a sticker of this and I'm deceased"
- "ok but why does [sticker concept] exist and why do I need 5"
- "my water bottle has never looked so good"
- Replying to someone's comment with "this energy right here" + mention
- "I saw a sticker that was literally this" (in response to a meme/quote)

## GENERATE 3 DRAFTS

For every thread, generate exactly 3 comment options:

1. **Link drop** (sticker_mention_style="link_drop" or "enthusiastic_share") -- \
   Includes the sticker URL naturally. Higher risk, higher reward. Only works in \
   threads where sharing links is normal.
2. **Subtle reference** (sticker_mention_style="subtle_reference") -- Mentions the \
   sticker concept without linking. Plants the seed. "I saw someone made a sticker \
   of this" without the URL.
3. **Pure engagement** (sticker_mention_style="no_mention") -- No sticker mention at \
   all. Just a good comment that builds the account's credibility in the community. \
   This is the long game.

## PLATFORM-SPECIFIC NOTES

- **Reddit**: Match the subreddit's culture. Some subs are formal, some are chaos. \
  Check if link-sharing is acceptable in that sub's culture.
- **YouTube**: Comments are shorter, more reaction-based. Timestamps and quotes from \
  the video land well.
- **TikTok**: Very short, emoji-heavy, often just reactions. "THE WAY I SCREAMED" energy.\
"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


def _build_model() -> GoogleModel:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(DEFAULT_MODEL, provider=provider)


comment_drafter_agent = Agent(
    model=_build_model(),
    system_prompt=SYSTEM_PROMPT,
    output_type=CommentDraftSet,
    model_settings=GoogleModelSettings(temperature=0.9, max_tokens=4096),
)


def draft_comments(
    sticker_text: str,
    sticker_url: str,
    thread_content: str,
    platform: str = "reddit",
) -> CommentDraftSet:
    """Draft 3 authentic-sounding comments for a thread that naturally mention a sticker.

    Args:
        sticker_text: What the sticker says or shows (e.g. "I burn for you" in Regency script).
        sticker_url: Link to the listing (can be placeholder).
        thread_content: The thread text -- title + top comments.
        platform: "reddit", "youtube", or "tiktok".
    """
    prompt_parts = [
        f"Sticker: {sticker_text}",
        f"Sticker URL: {sticker_url or '(no link yet)'}",
        f"Platform: {platform}",
        "",
        "--- THREAD CONTENT ---",
        thread_content,
        "--- END THREAD ---",
        "",
        "Draft 3 comments for this thread. Read the vibe carefully before writing. "
        "One with a natural link drop, one with a subtle reference, and one pure engagement "
        "(no sticker mention). Each must match the thread's exact tone and slang.",
    ]

    from utils.llm_retry import sync_retry_llm
    result = sync_retry_llm(lambda: comment_drafter_agent.run_sync("\n".join(prompt_parts)))
    return result.output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Draft authentic comments that naturally mention a sticker product"
    )
    parser.add_argument("sticker_text", help="What the sticker says/shows")
    parser.add_argument("sticker_url", nargs="?", default="", help="Link to the listing")
    parser.add_argument("--thread", default="", help="Thread text inline")
    parser.add_argument("--thread-file", type=Path, default=None, help="Path to thread text file")
    parser.add_argument("--platform", default="reddit", choices=["reddit", "youtube", "tiktok"])
    parser.add_argument("-o", "--out", type=Path, default=None)
    args = parser.parse_args()

    thread_content = args.thread
    if args.thread_file and args.thread_file.is_file():
        thread_content = args.thread_file.read_text(encoding="utf-8")

    if not thread_content.strip():
        print("Error: provide thread content via --thread or --thread-file")
        sys.exit(1)

    print(f"Drafting comments for sticker: {args.sticker_text}")
    print(f"Platform: {args.platform}")
    result = draft_comments(args.sticker_text, args.sticker_url, thread_content, args.platform)

    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
