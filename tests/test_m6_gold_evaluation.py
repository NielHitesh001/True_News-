"""Integration tests for M6 Corroboration Benchmark on Gold Set."""

from __future__ import annotations

import pytest
from scripts.evaluate_corroboration import main as run_corroboration_evaluation


def test_corroboration_gold_benchmark():
    results = run_corroboration_evaluation()

    # Total events processed == 11
    assert results["events_count"] == 11

    # Total canonical ledger entries >= 30
    assert results["total_ledger_entries"] >= 30

    # Contradictions identified > 0
    assert results["contradictions_detected"] > 0

    # Tier counts include Tier 1 and Tier 4
    assert results["tier_counts"]["PRIMARY_CONFIRMED"] > 0
    assert results["tier_counts"]["DISPUTED"] > 0
