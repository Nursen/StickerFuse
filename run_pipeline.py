"""StickerFuse Pipeline — CLI entry point.

Runs the full pipeline or individual stages:
  Topic → Subtopics → Viral Bites → Sticker Ideas → Design Specs

Usage:
  python run_pipeline.py mine-reddit --subreddits taylorswift --limit 10 -o output/reddit.json
  python run_pipeline.py mine-trends "Taylor Swift" -o output/trends.json
  python run_pipeline.py subtopics "Taylor Swift" --reddit-data output/reddit.json
  python run_pipeline.py viral-bites "Eras Tour final show" --context "Taylor Swift"
  python run_pipeline.py sticker-ideas "I'm the problem, it's me"
  python run_pipeline.py design "kawaii cat with 'I'm the problem' sign" --style kawaii
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_mine_reddit(args: argparse.Namespace) -> None:
    from miners.reddit_miner import mine_multiple_subreddits

    result = mine_multiple_subreddits(
        args.subreddits,
        limit=args.limit,
        sort=args.sort,
        time_filter=args.time_filter,
        include_comments=not args.no_comments,
    )
    _output(result, args.out)


def cmd_mine_trends(args: argparse.Namespace) -> None:
    from miners.trends_miner import mine_multiple_keywords

    result = mine_multiple_keywords(
        args.keywords,
        timeframe=args.timeframe,
        geo=args.geo,
    )
    _output(result, args.out)


def cmd_subtopics(args: argparse.Namespace) -> None:
    from agents.subtopic_agent import discover_subtopics

    reddit = _load_json(args.reddit_data) if args.reddit_data else None
    trends = _load_json(args.trends_data) if args.trends_data else None

    result = discover_subtopics(args.topic, reddit_data=reddit, trends_data=trends)
    _output(result.model_dump(), args.out)


def cmd_viral_bites(args: argparse.Namespace) -> None:
    from agents.viral_bite_agent import extract_viral_bites

    result = extract_viral_bites(args.subtopic, context=args.context)
    _output(result.model_dump(), args.out)


def cmd_sticker_ideas(args: argparse.Namespace) -> None:
    from agents.sticker_idea_agent import generate_sticker_ideas

    result = generate_sticker_ideas(args.viral_bite, context=args.context)
    _output(result.model_dump(), args.out)


def cmd_design(args: argparse.Namespace) -> None:
    from agents.design_agent import generate_design_spec

    result = generate_design_spec(args.concept, art_style=args.style, colors=args.colors)
    _output(result.model_dump(), args.out)


def _load_json(path: Path) -> dict | None:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _output(data: dict, out_path: Path | None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        print(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="StickerFuse: Viral Moments to Monetizable Merch"
    )
    subparsers = parser.add_subparsers(dest="command", help="Pipeline stage to run")

    # --- mine-reddit ---
    p = subparsers.add_parser("mine-reddit", help="Mine trending Reddit posts")
    p.add_argument("--subreddits", nargs="+", required=True)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--sort", choices=["hot", "top", "rising", "new"], default="hot")
    p.add_argument("--time-filter", default="week")
    p.add_argument("--no-comments", action="store_true")
    p.add_argument("-o", "--out", type=Path, default=None)

    # --- mine-trends ---
    p = subparsers.add_parser("mine-trends", help="Mine Google Trends data")
    p.add_argument("keywords", nargs="+")
    p.add_argument("--timeframe", default="now 7-d")
    p.add_argument("--geo", default="US")
    p.add_argument("-o", "--out", type=Path, default=None)

    # --- subtopics ---
    p = subparsers.add_parser("subtopics", help="Discover trending subtopics")
    p.add_argument("topic", help="Cultural topic to explore")
    p.add_argument("--reddit-data", type=Path, default=None)
    p.add_argument("--trends-data", type=Path, default=None)
    p.add_argument("-o", "--out", type=Path, default=None)

    # --- viral-bites ---
    p = subparsers.add_parser("viral-bites", help="Extract viral bites from a subtopic")
    p.add_argument("subtopic")
    p.add_argument("--context", default="")
    p.add_argument("-o", "--out", type=Path, default=None)

    # --- sticker-ideas ---
    p = subparsers.add_parser("sticker-ideas", help="Generate sticker concepts")
    p.add_argument("viral_bite")
    p.add_argument("--context", default="")
    p.add_argument("-o", "--out", type=Path, default=None)

    # --- design ---
    p = subparsers.add_parser("design", help="Generate image gen prompt for a sticker")
    p.add_argument("concept")
    p.add_argument("--style", default="")
    p.add_argument("--colors", default="")
    p.add_argument("-o", "--out", type=Path, default=None)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    commands = {
        "mine-reddit": cmd_mine_reddit,
        "mine-trends": cmd_mine_trends,
        "subtopics": cmd_subtopics,
        "viral-bites": cmd_viral_bites,
        "sticker-ideas": cmd_sticker_ideas,
        "design": cmd_design,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
