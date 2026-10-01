"""Unit tests for Source Registry (M1)."""

from __future__ import annotations

import pytest
from newsx.registry import SourceRegistry
from newsx.schemas import SourceTier, SourceStatus


def test_source_registry_loads_default_config():
    registry = SourceRegistry()
    sources = registry.all_sources()
    assert len(sources) >= 10, f"Expected at least 10 sources, got {len(sources)}"


def test_source_registry_tiers_coverage():
    registry = SourceRegistry()
    primary = registry.filter_by_tier(SourceTier.PRIMARY)
    secondary = registry.filter_by_tier(SourceTier.SECONDARY)
    tertiary = registry.filter_by_tier(SourceTier.TERTIARY)

    assert len(primary) >= 3, "Expected at least 3 primary sources"
    assert len(secondary) >= 5, "Expected at least 5 secondary sources"
    assert len(tertiary) >= 1, "Expected at least 1 tertiary source"


def test_source_registry_lookup():
    registry = SourceRegistry()
    reuters = registry.get("reuters")
    assert reuters is not None
    assert reuters.name == "Reuters"
    assert reuters.tier == SourceTier.SECONDARY
    assert reuters.full_text_retrievable is True

    ntsb = registry.get_or_raise("ntsb-gov")
    assert ntsb.tier == SourceTier.PRIMARY

    with pytest.raises(KeyError):
        registry.get_or_raise("non-existent-source-id")
