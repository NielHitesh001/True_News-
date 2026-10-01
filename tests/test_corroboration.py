"""Unit tests for Corroboration, Contradiction Detection, and Confidence Tiers (M6)."""

from __future__ import annotations

import pytest
from newsx.corroboration import Corroborator, IndependentOriginResolver
from newsx.schemas import Claim, ClaimStatus, ClaimType, ConfidenceTier, Item, Passage, PassageType, Source, SourceTier
from newsx.storage import Storage
from newsx.registry import SourceRegistry


@pytest.fixture
def corrob_env(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db", audit_path=tmp_path / "audit.jsonl")
    registry = SourceRegistry()
    for s in registry.all_sources():
        storage.save_source(s)
    corroborator = Corroborator(storage, registry)
    return corroborator, storage, registry


def test_independent_origin_counting_syndication_collapse(corrob_env):
    corroborator, storage, registry = corrob_env
    resolver = IndependentOriginResolver(storage, registry)

    # Wire original
    wire_item = Item(
        id="item-wire-1",
        source_id="reuters",
        url="https://reuters.com/1",
        title="Wire story",
        cleaned_text="Text",
        captured_time="2024-01-01T00:00:00Z",  # type: ignore
    )
    storage.save_item(wire_item)

    # Syndicated article (republished_from wire)
    synd_item = Item(
        id="item-synd-1",
        source_id="the-guardian",
        url="https://guardian.com/1",
        title="Syndicated story",
        cleaned_text="Text",
        captured_time="2024-01-01T00:00:00Z",  # type: ignore
        republished_from="item-wire-1",
    )
    storage.save_item(synd_item)

    c1 = Claim(id="c1", passage_id="p1", claim_type=ClaimType.EVENT, original_wording="Event text", provenance_chain=["reuters", "item-wire-1", "p1"])
    c2 = Claim(id="c2", passage_id="p2", claim_type=ClaimType.EVENT, original_wording="Event text", provenance_chain=["the-guardian", "item-synd-1", "p2"])

    ind_count, sources, has_primary = resolver.resolve([c1, c2])

    # Should count as 1 independent origin despite 2 outlets
    assert ind_count == 1
    assert sources == ["reuters", "the-guardian"]
    assert has_primary is False


def test_confidence_tier_primary_confirmed(corrob_env):
    corroborator, storage, registry = corrob_env

    item = Item(
        id="item-ntsb-1",
        source_id="ntsb-gov",
        url="https://ntsb.gov/1",
        title="NTSB Report",
        cleaned_text="Text",
        captured_time="2024-01-01T00:00:00Z",  # type: ignore
    )
    storage.save_item(item)

    passage = Passage(
        id="p-prim",
        item_id="item-ntsb-1",
        position=0,
        text="The NTSB reported six workers died in the collapse.",
        passage_type=PassageType.QUANTITATIVE,
    )
    storage.save_passages([passage])

    c_primary = Claim(
        id="c-prim",
        passage_id="p-prim",
        claim_type=ClaimType.EVENT,
        original_wording="The NTSB reported six workers died in the collapse.",
        neutralized_wording="The NTSB reported six workers died in the collapse.",
        provenance_chain=["ntsb-gov", "item-ntsb-1", "p-prim"],
    )
    storage.save_claim(c_primary)

    entries = corroborator.cluster_event_claims("event-test-prim", [c_primary], ["ntsb-gov"])
    assert len(entries) == 1
    assert entries[0].confidence_tier == ConfidenceTier.PRIMARY_CONFIRMED  # Tier 1


def test_confidence_tier_disputed_on_contradiction(corrob_env):
    corroborator, storage, registry = corrob_env

    c_a = Claim(
        id="c-a",
        passage_id="p-a",
        claim_type=ClaimType.STATEMENT,
        original_wording="Chinese coast guard vessels deliberately rammed and boarded Philippine naval boats.",
        neutralized_wording="Chinese coast guard vessels collided with and boarded Philippine naval boats.",
        provenance_chain=["reuters", "item-a", "p-a"],
    )
    c_b = Claim(
        id="c-b",
        passage_id="p-b",
        claim_type=ClaimType.STATEMENT,
        original_wording="The Philippine transport craft illegally intruded into Chinese territorial waters.",
        neutralized_wording="The Philippine transport craft illegally intruded into Chinese territorial waters.",
        provenance_chain=["reuters", "item-b", "p-b"],
    )

    entries = corroborator.cluster_event_claims("event-test-dispute", [c_a, c_b], ["reuters"])
    assert len(entries) == 2
    # Contradiction detected -> both become Tier 4 DISPUTED
    assert entries[0].confidence_tier == ConfidenceTier.DISPUTED
    assert entries[1].confidence_tier == ConfidenceTier.DISPUTED
    assert entries[0].contradictions == [entries[1].id]
    assert entries[1].contradictions == [entries[0].id]
