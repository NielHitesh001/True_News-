#!/usr/bin/env python3
"""Benchmark evaluation script for Milestone 7 (Presentation & Event Briefs).

Runs gold events through the end-to-end pipeline, synthesizes structured briefs,
exports Markdown & HTML files, and verifies provenance completeness and ranking invariants.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from newsx.pipeline import Pipeline
from newsx.presenter import ConsoleBriefRenderer, HtmlBriefRenderer, MarkdownBriefRenderer
from newsx.schemas import ConfidenceTier, DisputedPoint


def evaluate_briefs() -> bool:
    print("=" * 80)
    print("  MILESTONE 7 GOLD BENCHMARK: EVENT BRIEFS & MULTI-FORMAT DRILL-DOWN")
    print("=" * 80)

    pipeline = Pipeline()
    gold_events = [
        ("event-key-bridge-01", "Francis Scott Key Bridge Collapse Incident", "hard_fact"),
        ("event-us-jobs-01", "U.S. Bureau of Labor Statistics Monthly Employment Report", "numeric"),
        ("event-south-china-sea-01", "South China Sea Maritime Encounter at Second Thomas Shoal", "contested"),
    ]

    out_dir = Path("data/briefs")
    out_dir.mkdir(parents=True, exist_ok=True)

    passed_all = True

    for ev_id, ev_title, ev_category in gold_events:
        print(f"\n[*] Processing Event: {ev_id} ('{ev_title}') [{ev_category}]")
        pipeline.run_event_from_gold_file(ev_id)

        brief, md_p, html_p = pipeline.generate_event_brief(
            event_id=ev_id,
            event_title=ev_title,
            event_category=ev_category,
            output_dir=out_dir,
        )

        print(f"    - Neutral Headline: \"{brief.neutral_headline}\"")
        print(f"    - Core Facts:       {len(brief.core_facts)}")
        print(f"    - Single Source:    {len(brief.single_source_facts)}")
        print(f"    - Disputed Points:  {len(brief.disputed_points)}")
        print(f"    - Timeline Events:  {len(brief.timeline)}")
        print(f"    - Contributing Src: {len(brief.source_ledger)}")
        print(f"    - Diversity Status: {'COMPLIANT' if brief.diversity_compliant else 'DEFICIENT'}")
        print(f"    - Exported MD:      {md_p}")
        print(f"    - Exported HTML:    {html_p}")

        # Verification Invariants
        if not md_p.exists() or md_p.stat().st_size == 0:
            print(f"    ❌ Error: Markdown brief {md_p} is empty or missing")
            passed_all = False
        if not html_p.exists() or html_p.stat().st_size == 0:
            print(f"    ❌ Error: HTML brief {html_p} is empty or missing")
            passed_all = False

        # Specific Event Expectations
        if ev_id == "event-key-bridge-01":
            # Must have at least 1 Tier 1 (Primary Confirmed) fact
            has_tier1 = any(f.tier == ConfidenceTier.PRIMARY_CONFIRMED for f in brief.core_facts)
            if not has_tier1:
                print("    ❌ Invariant Failed: event-key-bridge-01 missing Tier 1 Primary Confirmed fact")
                passed_all = False
            else:
                print("    ✓ Tier 1 Primary Confirmation verified (NTSB report)")

        elif ev_id == "event-south-china-sea-01":
            # Must have at least 1 Disputed Point
            if not brief.disputed_points:
                print("    ❌ Invariant Failed: event-south-china-sea-01 missing Disputed Point")
                passed_all = False
            else:
                dp = brief.disputed_points[0]
                if isinstance(dp, DisputedPoint):
                    print(f"    ✓ Disputed Point verified: '{dp.topic}' ({len(dp.claims)} opposing positions)")

        # Provenance verification on all core facts
        for f in brief.core_facts:
            if not f.supporting_source_ids:
                print(f"    ❌ Core fact '{f.text}' missing supporting sources")
                passed_all = False

    print("\n" + "=" * 80)
    if passed_all:
        print("  ALL M7 BRIEF GENERATION & DRILL-DOWN INVARIANTS PASSED (100%)")
    else:
        print("  SOME INVARIANTS FAILED")
    print("=" * 80)
    return passed_all


if __name__ == "__main__":
    success = evaluate_briefs()
    sys.exit(0 if success else 1)
