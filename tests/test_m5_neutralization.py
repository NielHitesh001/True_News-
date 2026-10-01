"""Integration tests for M5 Neutralization Benchmark on Gold Set."""

from __future__ import annotations

import pytest
from scripts.evaluate_neutralization import main as run_neutralization_evaluation


def test_neutralization_gold_benchmark():
    results = run_neutralization_evaluation()

    # Change Traceability Rate == 1.0 (100% of edits have valid category, span, rationale)
    assert results["traceability_rate"] == 1.0, "Traceability rate is not 100%"

    # Meaning Preservation Rate >= 0.95
    assert results["meaning_rate"] >= 0.95, f"Meaning rate {results['meaning_rate']} < 0.95"

    # Factual Whitelist Preservation Rate == 1.0
    assert results["whitelist_rate"] == 1.0, f"Whitelist rate {results['whitelist_rate']} < 1.0"
