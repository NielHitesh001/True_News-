"""Unit tests for Diversity Checker & Quotas (M1)."""

from __future__ import annotations

import pytest
from newsx.registry import DiversityChecker, SourceRegistry
from newsx.transparency import generate_transparency_html, render_transparency_page


def test_diversity_evaluator_hard_fact_compliant():
    registry = SourceRegistry()
    checker = DiversityChecker(registry)

    # Compliant mix: 1 primary (ntsb-gov) + 2 secondary (reuters, ap-news)
    res = checker.evaluate("hard-fact", ["ntsb-gov", "reuters", "ap-news"])
    assert res.is_compliant is True
    assert len(res.deficiencies) == 0
    assert res.primary_count == 1
    assert res.secondary_count == 2
    assert res.distinct_ownership_count >= 2


def test_diversity_evaluator_missing_primary_deficiency():
    registry = SourceRegistry()
    checker = DiversityChecker(registry)

    # Non-compliant: 2 secondary only, missing primary for hard-fact
    res = checker.evaluate("hard-fact", ["reuters", "ap-news"])
    assert res.is_compliant is False
    assert any("Missing primary source" in d for d in res.deficiencies)


def test_diversity_evaluator_tertiary_ratio_violation():
    registry = SourceRegistry()
    checker = DiversityChecker(registry)

    # Non-compliant: tertiary aggregator included
    res = checker.evaluate("hard-fact", ["ntsb-gov", "reuters", "ap-news", "yahoo-news-aggregator"])
    assert res.is_compliant is False
    assert any("Excessive tertiary sources" in d for d in res.deficiencies)


def test_diversity_evaluator_contested_rules():
    registry = SourceRegistry()
    checker = DiversityChecker(registry)

    # Compliant contested mix: primary + 3 distinct secondaries across multiple regions
    res = checker.evaluate("contested", ["ecb-europa", "reuters", "bbc-news", "al-jazeera"])
    assert res.is_compliant is True
    assert res.distinct_region_count >= 2


def test_transparency_page_generation(tmp_path):
    registry = SourceRegistry()
    checker = DiversityChecker(registry)
    html_content = generate_transparency_html(registry, checker)

    assert "<!DOCTYPE html>" in html_content
    assert "Source Transparency Registry" in html_content
    assert "ntsb-gov" in html_content
    assert "reuters" in html_content
    assert "Event Diversity Quotas" in html_content

    # Test file output
    out_file = tmp_path / "transparency.html"
    res_path = render_transparency_page(out_file)
    assert res_path.exists()
    assert res_path.read_text(encoding="utf-8") == html_content
