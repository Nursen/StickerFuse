"""Dual-mode sentiment analyzer — VADER (free) + Gemini Flash-Lite (cheap).

VADER is the default for the scoring pipeline: instant, zero cost, good enough
for social-media text.  Gemini is opt-in for deeper emotion categories.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_vader = SentimentIntensityAnalyzer()


def _intensity_label(compound: float) -> str:
    """Categorize compound score into a human-readable intensity label."""
    if compound > 0.5:
        return "strong_positive"
    if compound > 0.05:
        return "positive"
    if compound >= -0.05:
        return "neutral"
    if compound >= -0.5:
        return "negative"
    return "strong_negative"


# ── VADER (free, instant) ────────────────────────────────────────────────────


def analyze_sentiment_vader(texts: list[str]) -> list[dict]:
    """Analyze sentiment of multiple texts using VADER (free, instant).

    Returns for each text a dict with compound, positive, negative, neutral,
    and an intensity label.
    """
    results: list[dict] = []
    for text in texts:
        scores = _vader.polarity_scores(text)
        results.append(
            {
                "text": text,
                "compound": scores["compound"],
                "positive": scores["pos"],
                "negative": scores["neg"],
                "neutral": scores["neu"],
                "intensity": _intensity_label(scores["compound"]),
            }
        )
    return results


def analyze_sentiment_batch(texts: list[str]) -> dict:
    """Analyze a batch of texts and return aggregate stats.

    Useful for getting a quick read on overall cluster sentiment without
    inspecting every individual post.
    """
    if not texts:
        return {
            "total_texts": 0,
            "avg_compound": 0.0,
            "sentiment_distribution": {
                "strong_positive": 0,
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "strong_negative": 0,
            },
            "emotional_intensity": 0.0,
            "most_positive": None,
            "most_negative": None,
        }

    per_text = analyze_sentiment_vader(texts)

    compounds = [r["compound"] for r in per_text]
    avg_compound = sum(compounds) / len(compounds)

    distribution: dict[str, int] = {
        "strong_positive": 0,
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "strong_negative": 0,
    }
    for r in per_text:
        distribution[r["intensity"]] += 1

    intense_count = sum(1 for c in compounds if abs(c) > 0.5)
    emotional_intensity = intense_count / len(compounds)

    most_positive = max(per_text, key=lambda r: r["compound"])
    most_negative = min(per_text, key=lambda r: r["compound"])

    return {
        "total_texts": len(texts),
        "avg_compound": round(avg_compound, 4),
        "sentiment_distribution": distribution,
        "emotional_intensity": round(emotional_intensity, 4),
        "most_positive": {"text": most_positive["text"], "compound": most_positive["compound"]},
        "most_negative": {"text": most_negative["text"], "compound": most_negative["compound"]},
    }


# ── Gemini Flash-Lite (cheap, deeper emotions) ──────────────────────────────

_EMOTION_LABELS = [
    "joy", "anger", "surprise", "nostalgia", "love",
    "fear", "disgust", "excitement", "sadness", "humor",
]

# Emotions that translate well to stickers (visual / quotable)
_HIGH_STICKER_EMOTIONS = {"excitement", "humor", "joy", "surprise", "love"}


def analyze_emotions_gemini(texts: list[str], max_texts: int = 20) -> list[dict]:
    """Use Gemini Flash-Lite for deeper emotion detection (cheap but costs money).

    Only analyze up to *max_texts* to control costs.  All texts are batched into
    a single prompt so we make exactly one API call.

    Requires GEMINI_API_KEY in the environment.
    """
    # Late import — don't force the dependency for VADER-only usage
    from pydantic_ai import Agent
    from pydantic_ai.models.google import GoogleModel

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY to use Gemini emotion analysis")

    truncated = texts[:max_texts]

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(truncated))
    prompt = (
        "Analyze the emotion in each numbered text below. "
        "For each text return a JSON object with:\n"
        '  "index": <1-based index>,\n'
        '  "primary_emotion": one of [joy, anger, surprise, nostalgia, love, fear, disgust, excitement, sadness, humor],\n'
        '  "emotions": {<emotion>: <float 0-1>, ...} (only include emotions with score > 0.1)\n'
        "\nReturn a JSON array of these objects, nothing else.\n\n"
        f"Texts:\n{numbered}"
    )

    model = GoogleModel("gemini-2.5-flash-lite", api_key=api_key)
    agent = Agent(model)
    result = agent.run_sync(prompt)

    # Parse the JSON from the response
    raw = result.output
    # Strip markdown code fences if present
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    parsed: list[dict] = json.loads(raw.strip())

    # Enrich with sticker_potential and original text
    results: list[dict] = []
    for item in parsed:
        idx = item.get("index", 0) - 1
        text = truncated[idx] if 0 <= idx < len(truncated) else ""
        primary = item.get("primary_emotion", "neutral")
        emotions = item.get("emotions", {})

        # Sticker potential: high if primary emotion is visual/quotable
        top_emotion_scores = sorted(emotions.values(), reverse=True)
        has_strong_emotion = top_emotion_scores and top_emotion_scores[0] >= 0.6
        is_visual = primary in _HIGH_STICKER_EMOTIONS

        if is_visual and has_strong_emotion:
            sticker_potential = "high"
        elif is_visual or has_strong_emotion:
            sticker_potential = "medium"
        else:
            sticker_potential = "low"

        results.append(
            {
                "text": text,
                "primary_emotion": primary,
                "emotions": emotions,
                "sticker_potential": sticker_potential,
            }
        )

    return results
