"""Mine community text for recurring phrases, in-jokes, and sticker-worthy moments.

Analyzes pasted chat logs, Discord exports, forum posts, etc. to find
phrases that a community repeats -- the raw material for niche stickers.

Usage:
  python -m miners.community_miner --file chat_export.txt
  python -m miners.community_miner --text "paste text here"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Common stop phrases to ignore -- conversational filler, not sticker material
_STOP_PHRASES = {
    "i think", "i don't", "i can't", "i just", "i mean", "you know",
    "it's like", "that's true", "i agree", "thank you", "thanks",
    "good morning", "good night", "see you", "talk later",
    "lol", "lmao", "haha", "hahaha", "yeah", "yep", "nah",
    "do you", "i was", "it was", "i have", "i had", "you are",
    "that was", "this is", "we are", "they are", "he was", "she was",
    "don't know", "going to", "want to", "have to", "need to",
    "right now", "a lot", "a lot of", "kind of", "sort of",
}


def _extract_messages(raw_text: str) -> list[str]:
    """Split raw text into individual messages.

    Handles common formats:
    - Discord export: "username -- date\\nmessage"
    - Slack export: "username  time\\nmessage"
    - Plain chat: one message per line
    - Forum: paragraphs separated by blank lines
    """
    lines = raw_text.strip().split("\n")
    messages: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) <= 2:
            continue

        # Discord header: "Username -- 04/18/2026 2:30 PM"
        if re.match(r"^[A-Za-z0-9_]+\s*[—\-]{1,2}\s*\d{1,2}/\d{1,2}/\d{2,4}", stripped):
            continue

        # Strip leading Discord/Slack-style username prefixes
        # "Username: message" or "[12:30] Username: message"
        cleaned = re.sub(r"^\[?\d{1,2}:\d{2}(?:\s*(?:AM|PM))?\]?\s*", "", stripped)
        cleaned = re.sub(r"^[A-Za-z0-9_]{2,25}:\s+", "", cleaned)

        if cleaned and len(cleaned) > 2:
            messages.append(cleaned)

    return messages


def _extract_ngrams(messages: list[str], n_range: tuple[int, int] = (2, 6)) -> Counter:
    """Extract n-grams (2-6 words) from messages and count occurrences."""
    ngram_counts: Counter = Counter()

    for msg in messages:
        words = re.findall(r"[a-z0-9']+", msg.lower())
        for n in range(n_range[0], min(n_range[1] + 1, len(words) + 1)):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i : i + n])
                if phrase not in _STOP_PHRASES and len(phrase) > 5:
                    ngram_counts[phrase] += 1

    return ngram_counts


def _deduplicate_subphrases(
    phrases: list[tuple[str, int]],
) -> list[tuple[str, int]]:
    """Remove subphrases when a longer phrase covers them.

    If "big brain energy" appears 5 times and "big brain" also appears 5 times,
    drop "big brain" since it's just a substring of the longer one. Keep the
    shorter phrase only if it appears significantly more often (2x+).
    """
    # Sort by phrase length descending so longer phrases are checked first
    sorted_phrases = sorted(phrases, key=lambda x: len(x[0]), reverse=True)
    kept: list[tuple[str, int]] = []
    removed_phrases: set[str] = set()

    for phrase, count in sorted_phrases:
        if phrase in removed_phrases:
            continue
        kept.append((phrase, count))
        # Mark shorter subphrases for removal if they don't appear much more often
        words = phrase.split()
        for n in range(2, len(words)):
            for i in range(len(words) - n + 1):
                sub = " ".join(words[i : i + n])
                # Find this subphrase in the original list
                for other_phrase, other_count in sorted_phrases:
                    if other_phrase == sub and other_count < count * 2:
                        removed_phrases.add(sub)

    return kept


def _extract_emoji_patterns(messages: list[str]) -> Counter:
    """Count emoji and emoticon usage."""
    emoji_pattern = re.compile(
        r"[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff"
        r"\U0001f1e0-\U0001f1ff\U00002702-\U000027b0\U000024c2-\U0001f251"
        r"\U0001f900-\U0001f9ff\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff]+"
    )
    counts: Counter = Counter()
    for msg in messages:
        for match in emoji_pattern.finditer(msg):
            counts[match.group()] += 1
        # Text emoticons
        for emoticon in re.findall(r"(?::\)|:\(|:D|:P|<3|xD|XD|:O|;\))", msg):
            counts[emoticon] += 1
    return counts


def mine_community_text(
    text: str,
    *,
    min_occurrences: int = 3,
    top_n: int = 20,
) -> dict:
    """Analyze community text for recurring phrases and sticker opportunities.

    Args:
        text: Raw community text (chat logs, forum posts, etc.)
        min_occurrences: Minimum times a phrase must appear to be considered.
        top_n: Return top N phrases.

    Returns dict with:
        - recurring_phrases: [{phrase, count, example_context, sentiment}]
        - emoji_patterns: [{emoji, count}]
        - community_stats: {total_messages, unique_phrases, avg_message_length}
        - sticker_candidates: phrases ranked by (frequency * sentiment_intensity)
    """
    messages = _extract_messages(text)

    if not messages:
        return {
            "source": "community_text",
            "error": "No messages could be extracted from the input text.",
            "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    # Extract and filter n-grams
    ngrams = _extract_ngrams(messages)
    recurring = [
        (phrase, count)
        for phrase, count in ngrams.most_common(top_n * 3)
        if count >= min_occurrences
    ]

    # Remove subphrases covered by longer phrases
    recurring = _deduplicate_subphrases(recurring)

    # Sentiment via VADER (free, instant)
    from miners.sentiment import analyze_sentiment_vader

    phrase_results: list[dict] = []
    for phrase, count in recurring[:top_n]:
        sentiment = analyze_sentiment_vader([phrase])[0]

        # Find an example message containing this phrase
        example = ""
        for msg in messages:
            if phrase in msg.lower():
                example = msg[:200]
                break

        phrase_results.append(
            {
                "phrase": phrase,
                "count": count,
                "example_context": example,
                "sentiment_compound": sentiment["compound"],
                "sentiment_label": sentiment["intensity"],
                # Sticker score: frequency * emotional punch (+ small baseline)
                "sticker_score": round(
                    count * (abs(sentiment["compound"]) + 0.1), 2
                ),
            }
        )

    # Sort by sticker_score descending
    phrase_results.sort(key=lambda x: x["sticker_score"], reverse=True)

    # Emoji patterns
    emojis = _extract_emoji_patterns(messages)
    emoji_results = [{"emoji": e, "count": c} for e, c in emojis.most_common(10)]

    # Stats
    avg_len = sum(len(m) for m in messages) / len(messages) if messages else 0

    return {
        "source": "community_text",
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "community_stats": {
            "total_messages": len(messages),
            "unique_recurring_phrases": len(phrase_results),
            "avg_message_length": round(avg_len, 1),
        },
        "recurring_phrases": phrase_results,
        "emoji_patterns": emoji_results,
        "sticker_candidates": phrase_results[:10],
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mine community text for recurring phrases and sticker opportunities"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="Path to a text file (chat export, etc.)")
    group.add_argument("--text", type=str, help="Raw text to analyze (paste directly)")

    parser.add_argument(
        "--min-occurrences",
        type=int,
        default=3,
        help="Minimum phrase frequency (default 3)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Return top N phrases (default 20)",
    )
    parser.add_argument(
        "-o", "--out",
        type=Path,
        default=None,
        help="Write JSON output to this file",
    )
    args = parser.parse_args()

    if args.file:
        if not args.file.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        text = args.file.read_text(encoding="utf-8")
    else:
        text = args.text

    print(f"Mining community text ({len(text)} chars)...")
    result = mine_community_text(
        text,
        min_occurrences=args.min_occurrences,
        top_n=args.top_n,
    )

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
