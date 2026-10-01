"""Test suite for Milestone 7 (Event Briefs & Drill-Down Exports)."""

from __future__ import annotations

from pathlib import Path
from newsx.pipeline import Pipeline
from newsx.schemas import ConfidenceTier, DisputedPoint


def test_m7_brief_generation_gold_benchmark(tmp_path):
    pipeline = Pipeline()
    out_dir = tmp_path / "briefs"

    # 1. Hard Fact Event
    pipeline.run_event_from_gold_file("event-key-bridge-01")
    brief_1, md_1, html_1 = pipeline.generate_event_brief(
        event_id="event-key-bridge-01",
        event_title="Francis Scott Key Bridge Collapse Incident",
        event_category="hard_fact",
        output_dir=out_dir,
    )

    assert brief_1.neutral_headline == "Francis Scott Key Bridge Collapse Incident"
    assert len(brief_1.core_facts) >= 1
    # Verify Tier 1 is present and ranked first
    assert brief_1.core_facts[0].tier == ConfidenceTier.PRIMARY_CONFIRMED
    assert "ntsb-gov" in brief_1.core_facts[0].supporting_source_ids
    assert md_1.exists() and md_1.stat().st_size > 0
    assert html_1.exists() and html_1.stat().st_size > 0

    # 2. Contested Event
    pipeline.run_event_from_gold_file("event-south-china-sea-01")
    brief_3, md_3, html_3 = pipeline.generate_event_brief(
        event_id="event-south-china-sea-01",
        event_title="South China Sea Maritime Encounter at Second Thomas Shoal",
        event_category="contested",
        output_dir=out_dir,
    )

    assert len(brief_3.disputed_points) >= 1
    dp = brief_3.disputed_points[0]
    assert isinstance(dp, DisputedPoint)
    assert len(dp.claims) >= 2
    assert md_3.exists() and md_3.stat().st_size > 0
    assert html_3.exists() and html_3.stat().st_size > 0
