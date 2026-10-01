"""Milestone 9 Full-System Benchmark Integration Test Suite."""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts and src to path
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from evaluate_all import run_full_system_benchmark


def test_m9_full_system_benchmark_passes():
    """Verifies that all sub-benchmarks and milestones (M0 through M8) pass with 100% compliance."""
    success = run_full_system_benchmark()
    assert success is True
