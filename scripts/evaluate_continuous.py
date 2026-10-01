#!/usr/bin/env python3
"""Benchmark evaluation script for Milestone 8 (Continuous & Multi-Event Pipeline).

Simulates continuous streaming ingestion across multiple unfolding events,
verifying dynamic tier promotions (Tier 3 -> Tier 2 -> Tier 1), dispute emergence,
publisher retractions, brief version history, and structured diff generation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from newsx.continuous import ContinuousEngine, EventMatcher
from newsx.pipeline import Pipeline
from newsx.registry import SourceRegistry
from newsx.schemas import ClaimStatus, ConfidenceTier, DisputedPoint
from newsx.storage import Storage


def evaluate_continuous() -> bool:
    print("=" * 80)
    print("  MILESTONE 8 GOLD BENCHMARK: CONTINUOUS & MULTI-EVENT PIPELINE SIMULATION")
    print("=" * 80)

    storage = Storage(db_path=Path("data/test_continuous.db"), audit_path=Path("data/test_continuous_audit.jsonl"))
    registry = SourceRegistry()
    for s in registry.all_sources():
        storage.save_source(s)

    pipeline = Pipeline(storage, registry)
    engine = ContinuousEngine(storage, registry)
    matcher = EventMatcher(storage)

    out_dir = Path("data/briefs/continuous")
    out_dir.mkdir(parents=True, exist_ok=True)

    passed_all = True

    # -------------------------------------------------------------
    # Step 1: Initial Ingestion Wave (Single Source Dispatches)
    # -------------------------------------------------------------
    print("\n[Wave 1] Ingesting initial breaking dispatches (Day 1)...")
    it1, _, cl1 = pipeline.process_raw_item(
        source_id="reuters",
        url="https://reuters.com/bridge-breaking",
        title="Cargo ship Dali collides with Key Bridge in Baltimore",
        raw_text="The container ship Dali struck the Francis Scott Key Bridge early Tuesday morning.\nSix workers are missing and presumed dead.",
        custom_id="stream-art-001",
    )
    ev_bridge, brief_1, diff_1 = engine.update_event_with_item(
        event_id="stream-bridge-01",
        item=it1,
        claims=cl1,
        output_dir=out_dir,
    )
    print(f"    ✓ Event 'stream-bridge-01' initialized with 1 item: {diff_1.summary_of_changes}")

    # -------------------------------------------------------------
    # Step 2: Second Wave (Corroborating Secondary Source: Tier 3 -> Tier 2)
    # -------------------------------------------------------------
    print("\n[Wave 2] Ingesting second independent secondary report (Day 2)...")
    it2, _, cl2 = pipeline.process_raw_item(
        source_id="ap-news",
        url="https://apnews.com/bridge-followup",
        title="Search suspended for six missing workers in Baltimore bridge disaster",
        raw_text="Emergency responders confirmed six road workers were missing and presumed dead following the Dali bridge strike on Tuesday.",
        custom_id="stream-art-002",
    )
    # Test event matcher
    matched_ev = matcher.match_event(it2.title, it2.cleaned_text)
    if matched_ev == "stream-bridge-01":
        print("    ✓ EventMatcher correctly routed article to 'stream-bridge-01'")
    else:
        print(f"    ❌ EventMatcher failed to route article (got {matched_ev})")
        passed_all = False

    _, brief_2, diff_2 = engine.update_event_with_item(
        event_id="stream-bridge-01",
        item=it2,
        claims=cl2,
        output_dir=out_dir,
    )
    print(f"    ✓ Brief updated: {diff_2.summary_of_changes}")
    has_corrob = any(f.tier == ConfidenceTier.INDEPENDENTLY_CORROBORATED for f in brief_2.core_facts)
    if has_corrob:
        print("    ✓ Confidence tier successfully upgraded to Tier 2 (Independently Corroborated)")
    else:
        print("    ❌ Invariant Failed: Expected Tier 2 corroboration")
        passed_all = False

    # -------------------------------------------------------------
    # Step 3: Third Wave (Official Primary Source: Tier 2 -> Tier 1)
    # -------------------------------------------------------------
    print("\n[Wave 3] Ingesting official NTSB primary investigation report (Day 3)...")
    it3, _, cl3 = pipeline.process_raw_item(
        source_id="ntsb-gov",
        url="https://ntsb.gov/investigations/DCA24MM031",
        title="NTSB Preliminary Collision Findings",
        raw_text="The NTSB confirmed six road workers died in the Francis Scott Key Bridge collapse after Dali lost electrical power.",
        custom_id="stream-art-003",
    )
    _, brief_3, diff_3 = engine.update_event_with_item(
        event_id="stream-bridge-01",
        item=it3,
        claims=cl3,
        output_dir=out_dir,
    )
    print(f"    ✓ Brief updated: {diff_3.summary_of_changes}")
    has_primary = any(f.tier == ConfidenceTier.PRIMARY_CONFIRMED for f in brief_3.core_facts)
    if has_primary:
        print("    ✓ Confidence tier successfully elevated to Tier 1 (Primary Confirmed)")
    else:
        print("    ❌ Invariant Failed: Expected Tier 1 Primary Confirmation")
        passed_all = False

    # -------------------------------------------------------------
    # Step 4: Contradiction & Dispute Wave (Second Thomas Shoal)
    # -------------------------------------------------------------
    print("\n[Wave 4] Ingesting contested opposing claims (South China Sea)...")
    it_ph, _, cl_ph = pipeline.process_raw_item(
        source_id="reuters",
        url="https://reuters.com/ph-claims",
        title="Philippines reports China coast guard rammed boats",
        raw_text="The Philippine military stated Chinese coast guard vessels deliberately rammed supply craft near Second Thomas Shoal.",
        custom_id="stream-shoal-001",
    )
    engine.update_event_with_item("stream-shoal-01", it_ph, cl_ph, event_category="contested", output_dir=out_dir)

    it_cn, _, cl_cn = pipeline.process_raw_item(
        source_id="ap-news",
        url="https://apnews.com/cn-claims",
        title="China states Philippine boats illegally intruded into sovereign waters",
        raw_text="China Coast Guard asserted that Philippine transport craft illegally intruded into sovereign waters and collided with Chinese vessels.",
        custom_id="stream-shoal-002",
    )
    _, brief_shoal, diff_shoal = engine.update_event_with_item(
        event_id="stream-shoal-01",
        item=it_cn,
        claims=cl_cn,
        event_category="contested",
        output_dir=out_dir,
    )
    print(f"    ✓ Contested event brief updated: {diff_shoal.summary_of_changes}")
    if len(brief_shoal.disputed_points) >= 1:
        dp = brief_shoal.disputed_points[0]
        if isinstance(dp, DisputedPoint):
            print(f"    ✓ Contradiction detected & isolated to Disputed Points: '{dp.topic}' ({len(dp.claims)} claims)")
    else:
        print("    ❌ Invariant Failed: Expected Disputed Point on conflicting statements")
        passed_all = False

    # -------------------------------------------------------------
    # Step 5: Retraction Propagation
    # -------------------------------------------------------------
    print("\n[Wave 5] Testing publisher retraction propagation...")
    it_err, _, cl_err = pipeline.process_raw_item(
        source_id="the-guardian",
        url="https://guardian.com/bad-report",
        title="Unverified claim regarding bridge structural defect",
        raw_text="Anonymous contractors alleged bridge sensors failed completely three days prior.",
        custom_id="stream-art-err",
    )
    engine.update_event_with_item("stream-bridge-01", it_err, cl_err, output_dir=out_dir)

    retraction_results = engine.handle_retraction(
        item_id="stream-art-err",
        reason="Source retracts unverified contractor allegation.",
        output_dir=out_dir,
    )
    if retraction_results:
        ev_ret, br_ret, df_ret = retraction_results[0]
        print(f"    ✓ Retraction processed: {df_ret.summary_of_changes}")
        # Verify retracted claim is rejected
        rejected_c = storage.get_claim(cl_err[0].id)
        if rejected_c and rejected_c.status == ClaimStatus.REJECTED:
            print("    ✓ Retracted claims successfully purged and flagged ClaimStatus.REJECTED")
        else:
            print("    ❌ Retracted claim status not marked REJECTED")
            passed_all = False

    print("\n" + "=" * 80)
    if passed_all:
        print("  ALL M8 CONTINUOUS PIPELINE INVARIANTS PASSED (100%)")
    else:
        print("  SOME INVARIANTS FAILED")
    print("=" * 80)
    return passed_all


if __name__ == "__main__":
    success = evaluate_continuous()
    sys.exit(0 if success else 1)
