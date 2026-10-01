"""CLI interface for running the news extraction pipeline and utilities."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import Pipeline
from .transparency import render_transparency_page


def main() -> None:
    parser = argparse.ArgumentParser(description="Raw News Extraction Tool CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Run command
    run_parser = subparsers.add_parser("run", help="Run pipeline on an event")
    run_parser.add_argument("--event", "-e", required=True, help="Event ID to run (or 'all')")

    # Transparency command
    subparsers.add_parser("transparency", help="Render static transparency HTML page")

    # Brief command
    brief_parser = subparsers.add_parser("brief", help="Generate and render event brief")
    brief_parser.add_argument("--event", "-e", required=True, help="Event ID to generate brief for")
    brief_parser.add_argument("--output-dir", "-o", default="data/briefs", help="Output directory for briefs")

    # Stats command
    subparsers.add_parser("stats", help="Display storage statistics")

    args = parser.parse_args()

    if args.command == "run":
        pipeline = Pipeline()
        print(f"[*] Running pipeline on event: {args.event}")
        event = pipeline.run_event_from_gold_file(args.event)
        print(f"[✓] Successfully processed event: {event.id}")
        print(f"    - Member items: {len(event.member_item_ids)}")
        for item_id in event.member_item_ids:
            item = pipeline.storage.get_item(item_id)
            passages = pipeline.storage.get_passages_for_item(item_id)
            print(f"      • {item_id}: '{item.title if item else 'N/A'}' ({len(passages)} passages)")

    elif args.command == "brief":
        pipeline = Pipeline()
        # First ensure event is processed
        pipeline.run_event_from_gold_file(args.event)
        out_dir = Path(args.output_dir)
        brief, md_p, html_p = pipeline.generate_event_brief(args.event, output_dir=out_dir)
        from .presenter import ConsoleBriefRenderer
        print(ConsoleBriefRenderer().render(brief))
        print(f"\n[✓] Exported Markdown Brief: {md_p}")
        print(f"[✓] Exported HTML Brief:     {html_p}")

    elif args.command == "transparency":
        out = render_transparency_page()
        print(f"[✓] Rendered source transparency registry to: {out}")

    elif args.command == "stats":
        pipeline = Pipeline()
        items = pipeline.storage.list_items()
        sources = pipeline.registry.all_sources()
        print(f"Registered Sources: {len(sources)}")
        print(f"Stored Items:       {len(items)}")


if __name__ == "__main__":
    main()
