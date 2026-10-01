"""Triage Gold Set Benchmark Evaluation Script (M3).

Evaluates the performance of the automated Triage stage against human gold-set labels (Pass A).
Computes Accuracy, Macro-F1, and Confusion Matrices for Article and Passage classifications.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from newsx.normalizer import Normalizer
from newsx.schemas import ArticleType, Item, PassageType
from newsx.storage import Storage
from newsx.triage import TriageEngine

GOLD_RAW_PATH = ROOT / "gold" / "raw" / "items.jsonl"
GOLD_LABELS_PATH = ROOT / "gold" / "labels" / "pass_a"


def compute_metrics(predicted: list[str], ground_truth: list[str]) -> dict[str, Any]:
    n = len(ground_truth)
    if n == 0 or len(predicted) != n:
        return {"accuracy": 0.0, "macro_f1": 0.0, "per_class": {}}

    correct = sum(1 for p, g in zip(predicted, ground_truth) if p == g)
    accuracy = correct / n

    classes = sorted(set(ground_truth) | set(predicted))
    per_class = {}
    f1_scores = []

    for c in classes:
        tp = sum(1 for p, g in zip(predicted, ground_truth) if p == c and g == c)
        fp = sum(1 for p, g in zip(predicted, ground_truth) if p == c and g != c)
        fn = sum(1 for p, g in zip(predicted, ground_truth) if p != c and g == c)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        f1_scores.append(f1)

        per_class[c] = {
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "support": sum(1 for g in ground_truth if g == c),
        }

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "total": n,
    }


def main() -> dict[str, Any]:
    # Temporary in-memory / scratch storage
    storage = Storage(db_path=ROOT / "data" / "triage_eval.db", audit_path=ROOT / "data" / "triage_audit.jsonl")
    from newsx.registry import SourceRegistry
    reg = SourceRegistry()
    for s in reg.all_sources():
        storage.save_source(s)
    normalizer = Normalizer(storage)
    triage_engine = TriageEngine(storage)

    # Load gold items
    with GOLD_RAW_PATH.open("r", encoding="utf-8") as f:
        raw_items = [json.loads(line) for line in f if line.strip()]

    # Load gold labels
    with (GOLD_LABELS_PATH / "articles.jsonl").open("r", encoding="utf-8") as f:
        gold_articles = {r["item_id"]: r["article_type"] for r in (json.loads(line) for line in f if line.strip())}

    with (GOLD_LABELS_PATH / "passages.jsonl").open("r", encoding="utf-8") as f:
        gold_passages = {
            (r["item_id"], r["passage_index"]): (r["passage_type"], r["feeds_fact_base"])
            for r in (json.loads(line) for line in f if line.strip())
        }

    pred_art_types: list[str] = []
    gold_art_types: list[str] = []

    pred_psg_types: list[str] = []
    gold_psg_types: list[str] = []

    pred_feed_flags: list[str] = []
    gold_feed_flags: list[str] = []

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
        art_res, psg_res_list = triage_engine.triage_item(item, passages)

        # Article ground truth vs prediction
        if item_id in gold_articles:
            pred_art_types.append(item.article_type.value)
            gold_art_types.append(gold_articles[item_id])

        # Passage ground truth vs prediction
        for psg, res in zip(passages, psg_res_list):
            key = (item_id, psg.position)
            if key in gold_passages:
                g_type, g_feed = gold_passages[key]
                pred_psg_types.append(psg.passage_type.value)
                gold_psg_types.append(g_type)

                pred_feed_flags.append("FEED" if res.feeds_fact_base else "DROP")
                gold_feed_flags.append("FEED" if g_feed else "DROP")

    art_metrics = compute_metrics(pred_art_types, gold_art_types)
    psg_metrics = compute_metrics(pred_psg_types, gold_psg_types)
    feed_metrics = compute_metrics(pred_feed_flags, gold_feed_flags)

    print("=" * 68)
    print("M3 TRIAGE BENCHMARK REPORT (vs GOLD SET PASS A)")
    print("=" * 68)
    print(f"Article Triage Accuracy:   {art_metrics['accuracy']:.4f}  |  Macro-F1: {art_metrics['macro_f1']:.4f} (N={art_metrics['total']})")
    for c, stats in art_metrics["per_class"].items():
        print(f"  • {c:12s} Precision: {stats['precision']:.3f} | Recall: {stats['recall']:.3f} | F1: {stats['f1']:.3f} (N={stats['support']})")

    print("-" * 68)
    print(f"Passage Triage Accuracy:   {psg_metrics['accuracy']:.4f}  |  Macro-F1: {psg_metrics['macro_f1']:.4f} (N={psg_metrics['total']})")
    for c, stats in psg_metrics["per_class"].items():
        print(f"  • {c:20s} Precision: {stats['precision']:.3f} | Recall: {stats['recall']:.3f} | F1: {stats['f1']:.3f} (N={stats['support']})")

    print("-" * 68)
    print(f"Fact-Base Routing Accuracy: {feed_metrics['accuracy']:.4f}  |  Macro-F1: {feed_metrics['macro_f1']:.4f}")
    print("=" * 68)

    # Cleanup eval scratch db
    if (ROOT / "data" / "triage_eval.db").exists():
        (ROOT / "data" / "triage_eval.db").unlink()
    if (ROOT / "data" / "triage_audit.jsonl").exists():
        (ROOT / "data" / "triage_audit.jsonl").unlink()

    return {
        "article_accuracy": art_metrics["accuracy"],
        "passage_accuracy": psg_metrics["accuracy"],
        "routing_accuracy": feed_metrics["accuracy"],
        "article_metrics": art_metrics,
        "passage_metrics": psg_metrics,
        "feed_metrics": feed_metrics,
    }


def evaluate_triage() -> dict[str, Any]:
    return main()


if __name__ == "__main__":
    main()
