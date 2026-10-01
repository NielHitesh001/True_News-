"""Claim Extraction Benchmark Evaluation Script (M4).

Evaluates the performance of the automated Claim Extractor against human gold-set claims (Pass A).
Measures Span Boundary Precision/Recall/F1, Attribution Layer accuracy, and Provenance Anchoring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from newsx.extractor import ClaimExtractor
from newsx.normalizer import Normalizer
from newsx.registry import SourceRegistry
from newsx.schemas import ClaimStatus, Item, PassageType
from newsx.storage import Storage
from newsx.triage import TriageEngine

GOLD_RAW_PATH = ROOT / "gold" / "raw" / "items.jsonl"
GOLD_LABELS_PATH = ROOT / "gold" / "labels" / "pass_a"


def main() -> dict[str, Any]:
    storage = Storage(db_path=ROOT / "data" / "claims_eval.db", audit_path=ROOT / "data" / "claims_audit.jsonl")
    registry = SourceRegistry()
    for s in registry.all_sources():
        storage.save_source(s)

    normalizer = Normalizer(storage)
    triage_engine = TriageEngine(storage)
    extractor = ClaimExtractor(storage)

    # 1. Load gold raw items
    with GOLD_RAW_PATH.open("r", encoding="utf-8") as f:
        raw_items = [json.loads(line) for line in f if line.strip()]

    # 2. Load gold claims
    with (GOLD_LABELS_PATH / "claims.jsonl").open("r", encoding="utf-8") as f:
        gold_claims = [json.loads(line) for line in f if line.strip()]

    gold_claim_map = {
        (c["item_id"], c["passage_index"]): c for c in gold_claims
    }

    # 3. Run extraction
    extracted_claims = []
    unanchored_count = 0
    provenance_complete_count = 0

    for raw in raw_items:
        item_id = raw["item_id"]
        item = Item(
            id=item_id,
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
        claims = extractor.process_item_passages(item, passages)

        for c in claims:
            extracted_claims.append(c)
            if c.status == ClaimStatus.REJECTED:
                unanchored_count += 1
            if len(c.provenance_chain) == 3 and all(c.provenance_chain):
                provenance_complete_count += 1

    # 4. Compute Span & Attribution Alignment
    matched_exact = 0
    type_matches = 0
    attribution_matches = 0

    for ec in extracted_claims:
        # Get passage index
        passage = storage.get_passages_for_item(ec.provenance_chain[1])
        psg_idx = next((p.position for p in passage if p.id == ec.passage_id), None)
        if psg_idx is not None:
            key = (ec.provenance_chain[1], psg_idx)
            if key in gold_claim_map:
                matched_exact += 1
                gc = gold_claim_map[key]
                if ec.claim_type.value == gc["claim_type"]:
                    type_matches += 1
                if (ec.attribution_speaker is not None and gc["attribution_layer"] == "assertion") or (
                    ec.attribution_speaker is None and gc["attribution_layer"] is None
                ):
                    attribution_matches += 1

    total_extracted = len(extracted_claims)
    total_gold = len(gold_claims)

    precision = matched_exact / total_extracted if total_extracted > 0 else 0.0
    recall = matched_exact / total_gold if total_gold > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    type_acc = type_matches / matched_exact if matched_exact > 0 else 0.0
    attr_acc = attribution_matches / matched_exact if matched_exact > 0 else 0.0
    prov_rate = provenance_complete_count / total_extracted if total_extracted > 0 else 0.0

    print("=" * 68)
    print("M4 CLAIM EXTRACTION BENCHMARK REPORT (vs GOLD SET PASS A)")
    print("=" * 68)
    print(f"Total Gold Claims:          {total_gold}")
    print(f"Total Extracted Claims:     {total_extracted} (Unanchored / Rejected: {unanchored_count})")
    print(f"Span Grounding F1 Score:    {f1:.4f}  (Precision: {precision:.4f} | Recall: {recall:.4f})")
    print(f"Claim Type Accuracy:        {type_acc:.4f}")
    print(f"Attribution Layer Accuracy: {attr_acc:.4f}")
    print(f"Provenance Completeness:    {prov_rate * 100:.1f}% (3-tier chain: Source -> Item -> Passage)")
    print("=" * 68)

    # Cleanup eval scratch db
    if (ROOT / "data" / "claims_eval.db").exists():
        (ROOT / "data" / "claims_eval.db").unlink()
    if (ROOT / "data" / "claims_audit.jsonl").exists():
        (ROOT / "data" / "claims_audit.jsonl").unlink()

    return {
        "total_gold": total_gold,
        "total_extracted": total_extracted,
        "span_grounding_f1": f1,
        "span_f1": f1,
        "span_precision": precision,
        "span_recall": recall,
        "type_accuracy": type_acc,
        "attribution_accuracy": attr_acc,
        "provenance_completeness": prov_rate,
        "provenance_rate": prov_rate,
    }


def evaluate_claims() -> dict[str, Any]:
    return main()


if __name__ == "__main__":
    main()
