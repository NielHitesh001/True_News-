"""Integration tests for M4 Claim Extraction Benchmark on Gold Set."""

from __future__ import annotations

import pytest
from scripts.evaluate_claims import main as run_claims_evaluation


def test_claim_extraction_gold_benchmark():
    results = run_claims_evaluation()

    # Span Grounding F1 >= 0.85
    f1 = results["span_f1"]
    assert f1 >= 0.85, f"Claim span F1 {f1:.4f} fell below 0.85 threshold"

    # Provenance rate == 1.0 (100% complete 3-tier provenance chains)
    prov = results["provenance_rate"]
    assert prov == 1.0, f"Provenance completeness {prov:.4f} is not 100%"

    # Total extracted claims > 0
    assert results["total_extracted"] > 0
