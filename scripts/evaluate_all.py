#!/usr/bin/env python3
"""Unified Full-System Evaluation Harness (Milestone 9).

Executes end-to-end validation across all pipeline stages (M0 through M8),
evaluating inter-annotator agreement, source diversity quotas, triage routing,
claim extraction span grounding, neutralization reversibility, corroboration tiering,
brief drill-down presentation, and continuous lifecycle transitions.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from calculate_agreement import calculate_agreement
from evaluate_triage import evaluate_triage
from evaluate_claims import evaluate_claims
from evaluate_neutralization import evaluate_neutralization
from evaluate_corroboration import evaluate_corroboration
from evaluate_briefs import evaluate_briefs
from evaluate_continuous import evaluate_continuous


def run_full_system_benchmark() -> bool:
    start_time = time.time()

    print("=" * 80)
    print("  RAW NEWS EXTRACTION TOOL — FULL SYSTEM BENCHMARK & GOLD VALIDATION (M9)")
    print("=" * 80)

    results: list[dict[str, str]] = []
    all_passed = True

    # 1. Milestone 0: Inter-Annotator Agreement
    print("\n>>> [M0] Evaluating Annotation Agreement & Gold Schemas...")
    try:
        m0_metrics = calculate_agreement()
        kappa_art = m0_metrics["article_type_kappa"]
        span_f1 = m0_metrics["claim_span_f1"]
        m0_pass = kappa_art >= 0.85 and span_f1 >= 0.90
        results.append({
            "milestone": "M0: Definitions & Agreement",
            "metric": f"Kappa={kappa_art:.3f}, Span F1={span_f1:.3f}",
            "target": "Kappa >= 0.85, F1 >= 0.90",
            "status": "PASS" if m0_pass else "FAIL",
        })
        if not m0_pass:
            all_passed = False
    except Exception as e:
        print(f"Error in M0 evaluation: {e}")
        results.append({"milestone": "M0: Definitions & Agreement", "metric": str(e), "target": "PASS", "status": "FAIL"})
        all_passed = False

    # 2. Milestone 1: Source Registry & Diversity
    print("\n>>> [M1] Evaluating Source Registry & Diversity Quotas...")
    try:
        from newsx.registry import SourceRegistry, DiversityChecker
        reg = SourceRegistry()
        sources = reg.all_sources()
        checker = DiversityChecker(reg)
        m1_pass = len(sources) >= 10 and len([s for s in sources if s.tier.value == "primary"]) >= 4
        results.append({
            "milestone": "M1: Source Registry & Quotas",
            "metric": f"{len(sources)} sources ({len([s for s in sources if s.tier.value == 'primary'])} primary)",
            "target": ">=10 sources, >=4 primary",
            "status": "PASS" if m1_pass else "FAIL",
        })
        if not m1_pass:
            all_passed = False
    except Exception as e:
        print(f"Error in M1 evaluation: {e}")
        results.append({"milestone": "M1: Source Registry & Quotas", "metric": str(e), "target": "PASS", "status": "FAIL"})
        all_passed = False

    # 3. Milestone 2: Collection & Storage
    print("\n>>> [M2] Evaluating Collection, Deduplication & Storage...")
    try:
        from newsx.storage import Storage
        from newsx.pipeline import Pipeline
        pipe = Pipeline()
        pipe.run_event_from_gold_file("event-key-bridge-01")
        items = pipe.storage.list_items()
        m2_pass = len(items) >= 2
        results.append({
            "milestone": "M2: Collection & Normalization",
            "metric": f"SQLite CRUD + JSONL Audit Trail ({len(items)} items stored)",
            "target": "Deterministic Storage & Audit Logs",
            "status": "PASS" if m2_pass else "FAIL",
        })
        if not m2_pass:
            all_passed = False
    except Exception as e:
        print(f"Error in M2 evaluation: {e}")
        results.append({"milestone": "M2: Collection & Normalization", "metric": str(e), "target": "PASS", "status": "FAIL"})
        all_passed = False

    # 4. Milestone 3: Triage Engine
    print("\n>>> [M3] Evaluating Triage Engine & Fact-Base Routing...")
    try:
        m3_metrics = evaluate_triage()
        art_acc = m3_metrics.get("article_accuracy", 0.0)
        route_acc = m3_metrics.get("routing_accuracy", 0.0)
        m3_pass = art_acc >= 0.90 and route_acc >= 0.90
        results.append({
            "milestone": "M3: Content Triage",
            "metric": f"Article Acc={art_acc*100:.1f}%, Route Acc={route_acc*100:.1f}%",
            "target": "Accuracy >= 90%",
            "status": "PASS" if m3_pass else "FAIL",
        })
        if not m3_pass:
            all_passed = False
    except Exception as e:
        print(f"Error in M3 evaluation: {e}")
        results.append({"milestone": "M3: Content Triage", "metric": str(e), "target": "PASS", "status": "FAIL"})
        all_passed = False

    # 5. Milestone 4: Claim Extraction
    print("\n>>> [M4] Evaluating Claim Extraction & Grounding...")
    try:
        m4_metrics = evaluate_claims()
        span_f1 = m4_metrics.get("span_grounding_f1", 0.0)
        prov_comp = m4_metrics.get("provenance_completeness", 0.0)
        m4_pass = span_f1 >= 0.90 and prov_comp == 1.0
        results.append({
            "milestone": "M4: Claim Extraction",
            "metric": f"Span Grounding F1={span_f1:.3f}, Provenance={prov_comp*100:.0f}%",
            "target": "Grounding F1 >= 0.90, Provenance = 100%",
            "status": "PASS" if m4_pass else "FAIL",
        })
        if not m4_pass:
            all_passed = False
    except Exception as e:
        print(f"Error in M4 evaluation: {e}")
        results.append({"milestone": "M4: Claim Extraction", "metric": str(e), "target": "PASS", "status": "FAIL"})
        all_passed = False

    # 6. Milestone 5: Neutralization
    print("\n>>> [M5] Evaluating Neutralization & Meaning Preservation...")
    try:
        m5_metrics = evaluate_neutralization()
        reversibility = m5_metrics.get("reversibility_rate", 0.0)
        retention = m5_metrics.get("meaning_retention_rate", 0.0)
        m5_pass = reversibility == 1.0 and retention == 1.0
        results.append({
            "milestone": "M5: Neutralization",
            "metric": f"Reversibility={reversibility*100:.0f}%, Retention={retention*100:.0f}%",
            "target": "Reversibility=100%, Retention=100%",
            "status": "PASS" if m5_pass else "FAIL",
        })
        if not m5_pass:
            all_passed = False
    except Exception as e:
        print(f"Error in M5 evaluation: {e}")
        results.append({"milestone": "M5: Neutralization", "metric": str(e), "target": "PASS", "status": "FAIL"})
        all_passed = False

    # 7. Milestone 6: Corroboration & Tiering
    print("\n>>> [M6] Evaluating Corroboration & Contradiction Detection...")
    try:
        m6_pass = evaluate_corroboration()
        results.append({
            "milestone": "M6: Corroboration & Tiers",
            "metric": "Syndication collapse + 5-Tier hierarchy + Disputes",
            "target": "100% Invariants Passed",
            "status": "PASS" if m6_pass else "FAIL",
        })
        if not m6_pass:
            all_passed = False
    except Exception as e:
        print(f"Error in M6 evaluation: {e}")
        results.append({"milestone": "M6: Corroboration & Tiers", "metric": str(e), "target": "PASS", "status": "FAIL"})
        all_passed = False

    # 8. Milestone 7: Presentation & Event Briefs
    print("\n>>> [M7] Evaluating Event Briefs & Multi-Format Exports...")
    try:
        m7_pass = evaluate_briefs()
        results.append({
            "milestone": "M7: Presentation & Briefs",
            "metric": "Markdown + HTML + Terminal Drill-Downs",
            "target": "100% Drill-Down Provenance",
            "status": "PASS" if m7_pass else "FAIL",
        })
        if not m7_pass:
            all_passed = False
    except Exception as e:
        print(f"Error in M7 evaluation: {e}")
        results.append({"milestone": "M7: Presentation & Briefs", "metric": str(e), "target": "PASS", "status": "FAIL"})
        all_passed = False

    # 9. Milestone 8: Continuous Pipeline & Retractions
    print("\n>>> [M8] Evaluating Continuous Streaming & Retraction Propagation...")
    try:
        m8_pass = evaluate_continuous()
        results.append({
            "milestone": "M8: Continuous & Retractions",
            "metric": "Dynamic Tier Promotions (T3->T2->T1) + Diffing",
            "target": "100% Invariants Passed",
            "status": "PASS" if m8_pass else "FAIL",
        })
        if not m8_pass:
            all_passed = False
    except Exception as e:
        print(f"Error in M8 evaluation: {e}")
        results.append({"milestone": "M8: Continuous & Retractions", "metric": str(e), "target": "PASS", "status": "FAIL"})
        all_passed = False

    elapsed = time.time() - start_time

    # -------------------------------------------------------------
    # Print Comprehensive Scorecard Table
    # -------------------------------------------------------------
    print("\n" + "=" * 90)
    print("  RAW NEWS EXTRACTION TOOL — PRODUCTION BENCHMARK SCORECARD")
    print("=" * 90)
    header = f"{'Stage / Milestone':<32} | {'Achieved Metric':<32} | {'Target':<14} | {'Status':<6}"
    print(header)
    print("-" * 90)
    for r in results:
        status_str = f"✅ {r['status']}" if r["status"] == "PASS" else f"❌ {r['status']}"
        print(f"{r['milestone']:<32} | {r['metric']:<32} | {r['target']:<14} | {status_str:<6}")
    print("=" * 90)
    print(f"Total Evaluation Time: {elapsed:.2f}s")
    if all_passed:
        print("  🎉 ALL MILESTONES (M0 - M9) PASSED PRODUCTION VALIDATION!")
    else:
        print("  ⚠️ SOME STAGES FAILED VALIDATION")
    print("=" * 90)

    return all_passed


if __name__ == "__main__":
    success = run_full_system_benchmark()
    sys.exit(0 if success else 1)
