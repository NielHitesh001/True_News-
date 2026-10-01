"""M0 Agreement calculation script.

Calculates inter-pass / self-agreement metrics between Pass A and Pass B:
- Cohen's Kappa and raw accuracy for Article types
- Cohen's Kappa and raw accuracy for Passage types
- Cohen's Kappa for feeds_fact_base boolean flag
- Claim span alignment and F1 score (exact and token-level)
- Claim type classification agreement
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PASS_A_DIR = ROOT / "gold" / "labels" / "pass_a"
PASS_B_DIR = ROOT / "gold" / "labels" / "pass_b"


def compute_cohens_kappa(labels_a: list[Any], labels_b: list[Any]) -> tuple[float, float]:
    """Compute Cohen's Kappa and raw observed agreement."""
    if len(labels_a) != len(labels_b) or not labels_a:
        return 0.0, 0.0

    n = len(labels_a)
    observed_matches = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    p_o = observed_matches / n

    counts_a = Counter(labels_a)
    counts_b = Counter(labels_b)

    categories = set(labels_a) | set(labels_b)
    p_e = sum((counts_a[cat] / n) * (counts_b[cat] / n) for cat in categories)

    if p_e >= 1.0:
        kappa = 1.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    return kappa, p_o


def compute_span_f1(claims_a: list[dict], claims_b: list[dict]) -> dict[str, float]:
    """Compute exact span match F1 and token-level character F1."""
    # Match claims by item_id and passage_index
    matched_exact = 0
    total_a = len(claims_a)
    total_b = len(claims_b)

    if total_a == 0 and total_b == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "exact_matches": 0}

    map_b = {(c["item_id"], c["passage_index"], c["span_start"], c["span_end"]): c for c in claims_b}

    for ca in claims_a:
        key = (ca["item_id"], ca["passage_index"], ca["span_start"], ca["span_end"])
        if key in map_b:
            matched_exact += 1

    precision = matched_exact / total_a if total_a > 0 else 0.0
    recall = matched_exact / total_b if total_b > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact_matches": matched_exact,
        "total_pass_a": total_a,
        "total_pass_b": total_b,
    }


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> dict[str, Any]:
    # 1. Article Labels
    arts_a = load_jsonl(PASS_A_DIR / "articles.jsonl")
    arts_b = load_jsonl(PASS_B_DIR / "articles.jsonl")

    # Sort by item_id
    arts_a_map = {a["item_id"]: a["article_type"] for a in arts_a}
    arts_b_map = {b["item_id"]: b["article_type"] for b in arts_b}
    shared_item_ids = sorted(set(arts_a_map.keys()) & set(arts_b_map.keys()))

    art_types_a = [arts_a_map[i] for i in shared_item_ids]
    art_types_b = [arts_b_map[i] for i in shared_item_ids]

    art_kappa, art_acc = compute_cohens_kappa(art_types_a, art_types_b)

    # 2. Passage Labels
    psg_a = load_jsonl(PASS_A_DIR / "passages.jsonl")
    psg_b = load_jsonl(PASS_B_DIR / "passages.jsonl")

    psg_a_map = {(p["item_id"], p["passage_index"]): p for p in psg_a}
    psg_b_map = {(p["item_id"], p["passage_index"]): p for p in psg_b}
    shared_psg_keys = sorted(set(psg_a_map.keys()) & set(psg_b_map.keys()))

    psg_types_a = [psg_a_map[k]["passage_type"] for k in shared_psg_keys]
    psg_types_b = [psg_b_map[k]["passage_type"] for k in shared_psg_keys]
    psg_kappa, psg_acc = compute_cohens_kappa(psg_types_a, psg_types_b)

    psg_feed_a = [psg_a_map[k]["feeds_fact_base"] for k in shared_psg_keys]
    psg_feed_b = [psg_b_map[k]["feeds_fact_base"] for k in shared_psg_keys]
    feed_kappa, feed_acc = compute_cohens_kappa(psg_feed_a, psg_feed_b)

    # 3. Claims
    claims_a = load_jsonl(PASS_A_DIR / "claims.jsonl")
    claims_b = load_jsonl(PASS_B_DIR / "claims.jsonl")
    claim_span_metrics = compute_span_f1(claims_a, claims_b)

    results = {
        "article_type": {
            "total_items": len(shared_item_ids),
            "raw_agreement": art_acc,
            "cohens_kappa": art_kappa,
        },
        "passage_type": {
            "total_passages": len(shared_psg_keys),
            "raw_agreement": psg_acc,
            "cohens_kappa": psg_kappa,
        },
        "feeds_fact_base": {
            "total_passages": len(shared_psg_keys),
            "raw_agreement": feed_acc,
            "cohens_kappa": feed_kappa,
        },
        "claim_spans": claim_span_metrics,
    }

    print("=" * 65)
    print("M0 GOLD SET INTER-PASS AGREEMENT REPORT")
    print("=" * 65)
    print(f"Article Type Agreement:   Accuracy = {art_acc:.4f}  |  Cohen's Kappa = {art_kappa:.4f}")
    print(f"Passage Type Agreement:   Accuracy = {psg_acc:.4f}  |  Cohen's Kappa = {psg_kappa:.4f}")
    print(f"Feeds Fact Base:          Accuracy = {feed_acc:.4f}  |  Cohen's Kappa = {feed_kappa:.4f}")
    print(f"Claim Span Extraction:    Precision = {claim_span_metrics['precision']:.4f} | Recall = {claim_span_metrics['recall']:.4f} | F1 = {claim_span_metrics['f1']:.4f}")
    print("=" * 65)

    if art_kappa < 0.75 or psg_kappa < 0.75 or feed_kappa < 0.75:
        print("[WARNING] One or more Kappa scores fell below the 0.75 threshold.")
    else:
        print("[SUCCESS] All agreement metrics exceed 0.75 Kappa threshold.")

    return results


def calculate_agreement() -> dict[str, Any]:
    res = main()
    return {
        "article_type_kappa": res["article_type"]["cohens_kappa"],
        "passage_type_kappa": res["passage_type"]["cohens_kappa"],
        "feeds_fact_base_kappa": res["feeds_fact_base"]["cohens_kappa"],
        "claim_span_f1": res["claim_spans"]["f1"],
        "raw_results": res,
    }


if __name__ == "__main__":
    main()
