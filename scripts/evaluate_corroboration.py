"""Corroboration and Clustering Benchmark Evaluation Script (M6).

Evaluates the performance of the automated Corroboration engine:
- Event clustering into canonical LedgerEntry records
- Independent-origin calculation (collapsing syndicated copy)
- Contradiction identification across conflicting claims (Tier 4)
- Confidence tier calibration (Tiers 1 to 5)
- Omission tracking across outlets
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from newsx.pipeline import Pipeline
from newsx.registry import SourceRegistry
from newsx.schemas import ConfidenceTier
from newsx.storage import Storage

GOLD_RAW_PATH = ROOT / "gold" / "raw" / "items.jsonl"


def main() -> dict[str, Any]:
    storage = Storage(db_path=ROOT / "data" / "corrob_eval.db", audit_path=ROOT / "data" / "corrob_audit.jsonl")
    registry = SourceRegistry()
    for s in registry.all_sources():
        storage.save_source(s)

    pipeline = Pipeline(storage=storage, registry=registry)

    # 1. Discover events in gold set
    with GOLD_RAW_PATH.open("r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    events = sorted(set(item["event_id"] for item in items if "event_id" in item))

    total_ledger_entries = 0
    tier_counts = {tier.name: 0 for tier in ConfidenceTier}
    contradictions_detected = 0
    omissions_detected = 0

    for ev_id in events:
        event = pipeline.run_event_from_gold_file(ev_id)
        # Retrieve ledger entries generated
        entries = [
            storage.get_ledger_entry(r.id)
            for r in storage.list_ledger_entries()
            if r.id.startswith(f"ledger-{ev_id}")
        ]

        total_ledger_entries += len(entries)
        for e in entries:
            tier_counts[e.confidence_tier.name] += 1
            if e.contradictions:
                contradictions_detected += len(e.contradictions)
            if e.omissions:
                omissions_detected += len(e.omissions)

    print("=" * 68)
    print("M6 CLUSTERING & CORROBORATION BENCHMARK REPORT")
    print("=" * 68)
    print(f"Total Events Processed:        {len(events)}")
    print(f"Total Canonical Ledger Claims: {total_ledger_entries}")
    print(f"Contradictions Identified:     {contradictions_detected // 2} disputed pairs")
    print(f"Omission Links Tracked:        {omissions_detected}")
    print("-" * 68)
    print("Confidence Tier Distribution:")
    for tier_name, count in tier_counts.items():
        pct = (count / total_ledger_entries * 100) if total_ledger_entries > 0 else 0.0
        print(f"  • {tier_name:28s}: {count:3d} ({pct:5.1f}%)")
    print("=" * 68)

    # Cleanup eval scratch db
    if (ROOT / "data" / "corrob_eval.db").exists():
        (ROOT / "data" / "corrob_eval.db").unlink()
    if (ROOT / "data" / "corrob_audit.jsonl").exists():
        (ROOT / "data" / "corrob_audit.jsonl").unlink()

    return {
        "events_count": len(events),
        "total_ledger_entries": total_ledger_entries,
        "tier_counts": tier_counts,
        "contradictions_detected": contradictions_detected // 2,
        "omissions_detected": omissions_detected,
    }


def evaluate_corroboration() -> bool:
    res = main()
    return res["total_ledger_entries"] > 0 and res["contradictions_detected"] > 0


if __name__ == "__main__":
    main()
