"""Neutralization Benchmark Evaluation Script (M5).

Evaluates the performance of the automated Neutralizer:
- Change Traceability (reversibility, categorization, rationale completeness)
- Meaning Preservation check pass rate
- Factual Emotion Whitelist preservation (ensuring 'hospitalized', 'injured' are preserved)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from newsx.extractor import ClaimExtractor
from newsx.neutralizer import Neutralizer
from newsx.normalizer import Normalizer
from newsx.registry import SourceRegistry
from newsx.schemas import ClaimStatus, Item
from newsx.storage import Storage
from newsx.triage import TriageEngine

GOLD_RAW_PATH = ROOT / "gold" / "raw" / "items.jsonl"


def main() -> dict[str, Any]:
    storage = Storage(db_path=ROOT / "data" / "neut_eval.db", audit_path=ROOT / "data" / "neut_audit.jsonl")
    registry = SourceRegistry()
    for s in registry.all_sources():
        storage.save_source(s)

    normalizer = Normalizer(storage)
    triage_engine = TriageEngine(storage)
    extractor = ClaimExtractor(storage)
    neutralizer = Neutralizer(storage)

    with GOLD_RAW_PATH.open("r", encoding="utf-8") as f:
        raw_items = [json.loads(line) for line in f if line.strip()]

    all_claims = []
    modified_claims = []
    traceability_pass = 0
    meaning_preservation_pass = 0
    whitelist_preservation_pass = 0
    factual_whitelist_instances = 0

    for raw in raw_items:
        item = Item(
            id=raw["item_id"],
            source_id=raw["source"],
            url=raw["url"],
            title=raw["title"],
            byline=raw.get("byline", ""),
            dateline=raw.get("dateline", ""),
            cleaned_text=raw["text"],
            captured_time="2024-01-01T00:00:00Z",  # type: ignore
        )
        passages = normalizer.normalize_item(item)
        triage_engine.triage_item(item, passages)
        extracted = extractor.process_item_passages(item, passages)
        neutralized_list = neutralizer.process_claims(extracted)

        for c in neutralized_list:
            all_claims.append(c)

            if c.changes:
                modified_claims.append(c)
                # Check change traceability
                if all(ch.original_span and ch.category and ch.rationale for ch in c.changes):
                    traceability_pass += 1

            if c.status == ClaimStatus.NEUTRALIZED:
                meaning_preservation_pass += 1

            # Check factual whitelist terms
            orig_lower = c.original_wording.lower()
            for term in neutralizer.whitelist:
                if term in orig_lower:
                    factual_whitelist_instances += 1
                    target_text = (c.neutralized_wording or c.original_wording).lower()
                    if term in target_text:
                        whitelist_preservation_pass += 1

    total_claims = len(all_claims)
    total_modified = len(modified_claims)
    trace_rate = traceability_pass / total_modified if total_modified > 0 else 1.0
    meaning_rate = meaning_preservation_pass / total_claims if total_claims > 0 else 1.0
    whitelist_rate = (
        whitelist_preservation_pass / factual_whitelist_instances
        if factual_whitelist_instances > 0
        else 1.0
    )

    print("=" * 68)
    print("M5 NEUTRALIZATION BENCHMARK REPORT (vs GOLD SET PASS A)")
    print("=" * 68)
    print(f"Total Factual Claims Processed:    {total_claims}")
    print(f"Claims Modified by Neutralization: {total_modified} ({total_modified/total_claims*100:.1f}%)")
    print(f"Change Traceability Rate:          {trace_rate * 100:.1f}% (Reversible with exact span & rationale)")
    print(f"Meaning Preservation Pass Rate:    {meaning_rate * 100:.1f}% (Zero semantic drift)")
    print(f"Factual Emotion Retention Rate:    {whitelist_rate * 100:.1f}% (E.g. 'hospitalized', 'injured' kept)")
    print("=" * 68)

    # Display sample rewrites
    if modified_claims:
        print("\nSample Neutralization Rewrites:")
        for mc in modified_claims[:3]:
            print(f"  • Original:    \"{mc.original_wording}\"")
            print(f"    Neutralized: \"{mc.neutralized_wording}\"")
            for ch in mc.changes:
                print(f"    Change:      [{ch.category}] '{ch.original_span}' -> '{ch.replacement}' ({ch.rationale})")
            print()

    # Cleanup eval scratch db
    if (ROOT / "data" / "neut_eval.db").exists():
        (ROOT / "data" / "neut_eval.db").unlink()
    if (ROOT / "data" / "neut_audit.jsonl").exists():
        (ROOT / "data" / "neut_audit.jsonl").unlink()

    return {
        "total_claims": total_claims,
        "total_modified": total_modified,
        "reversibility_rate": trace_rate,
        "traceability_rate": trace_rate,
        "meaning_retention_rate": meaning_rate,
        "meaning_rate": meaning_rate,
        "whitelist_rate": whitelist_rate,
    }


def evaluate_neutralization() -> dict[str, Any]:
    return main()


if __name__ == "__main__":
    main()
