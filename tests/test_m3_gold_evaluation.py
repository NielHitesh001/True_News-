"""Integration tests for M3 Triage Benchmark on Gold Set."""

from __future__ import annotations

from pathlib import Path
import pytest
from scripts.evaluate_triage import main as run_triage_evaluation


def test_triage_gold_benchmark_accuracy_thresholds():
    results = run_triage_evaluation()

    # Article level accuracy >= 0.90
    art_acc = results["article_metrics"]["accuracy"]
    assert art_acc >= 0.90, f"Article accuracy {art_acc:.4f} fell below 0.90 threshold"

    # Fact base routing accuracy >= 0.95
    feed_acc = results["feed_metrics"]["accuracy"]
    assert feed_acc >= 0.95, f"Fact base routing accuracy {feed_acc:.4f} fell below 0.95 threshold"

    # Passage level accuracy >= 0.80
    psg_acc = results["passage_metrics"]["accuracy"]
    assert psg_acc >= 0.80, f"Passage accuracy {psg_acc:.4f} fell below 0.80 threshold"
