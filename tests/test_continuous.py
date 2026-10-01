"""Unit tests for Continuous Pipeline, Evolution, Retractions & Diffing (M8)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from newsx.continuous import ContinuousEngine, EventMatcher
from newsx.pipeline import Pipeline
from newsx.registry import SourceRegistry
from newsx.schemas import (
    ArticleType,
    BriefFact,
    Claim,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    Event,
    Item,
    Passage,
    PassageType,
)
from newsx.storage import Storage


@pytest.fixture
def cont_env(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db", audit_path=tmp_path / "audit.jsonl")
    registry = SourceRegistry()
    for s in registry.all_sources():
        storage.save_source(s)
    engine = ContinuousEngine(storage, registry)
    pipeline = Pipeline(storage, registry)
    return engine, pipeline, storage, registry


def test_event_matcher_finds_related_event(cont_env):
    engine, pipeline, storage, registry = cont_env
    matcher = EventMatcher(storage)

    event = Event(
        id="ev-bridge-test",
        label="Baltimore Key Bridge Dali Collision",
        member_item_ids=[],
        time_span=(None, None),
        claim_ids=[],
    )
    storage.save_event(event)

    item = Item(
        id="it-1",
        source_id="reuters",
        url="https://reuters.com/1",
        title="Dali cargo ship strikes Key Bridge in Baltimore disaster",
        cleaned_text="The container ship Dali struck a support pillar of the Francis Scott Key Bridge.",
        captured_time="2024-03-26T00:00:00Z",  # type: ignore
    )
    storage.save_item(item)
    event.member_item_ids.append(item.id)
    storage.save_event(event)

    # Match candidate new article
    matched_ev = matcher.match_event(
        item_title="Key Bridge wreckage salvage begins in Baltimore",
        item_text="Crews began removing debris from the container ship Dali and the collapsed bridge.",
    )
    assert matched_ev == "ev-bridge-test"


def test_continuous_tier_promotion_tier3_to_tier2(cont_env, tmp_path):
    engine, pipeline, storage, registry = cont_env

    # 1. Ingest initial single-source article
    item_1, p_1, claims_1 = pipeline.process_raw_item(
        source_id="reuters",
        url="https://reuters.com/bridge-1",
        title="Key Bridge Incident",
        raw_text="Six workers were reported missing after the bridge collapsed on Tuesday.",
        custom_id="it-reuters-1",
    )
    event, brief_1, diff_1 = engine.update_event_with_item(
        event_id="ev-bridge-update",
        item=item_1,
        claims=claims_1,
        output_dir=tmp_path / "briefs",
    )

    # Initial state: single source
    assert len(event.member_item_ids) == 1
    assert len(brief_1.single_source_facts) >= 1 or len(brief_1.core_facts) >= 1

    # 2. Ingest 2nd independent secondary article
    item_2, p_2, claims_2 = pipeline.process_raw_item(
        source_id="ap-news",
        url="https://apnews.com/bridge-2",
        title="Key Bridge Search Continues",
        raw_text="Authorities confirmed that six workers were missing after the bridge collapse on Tuesday.",
        custom_id="it-ap-2",
    )
    event_updated, brief_2, diff_2 = engine.update_event_with_item(
        event_id="ev-bridge-update",
        item=item_2,
        claims=claims_2,
        output_dir=tmp_path / "briefs",
    )

    assert len(event_updated.member_item_ids) == 2
    # Should now have corroborated Core Facts (Tier 2)
    assert len(brief_2.core_facts) >= 1
    top_fact = brief_2.core_facts[0]
    assert top_fact.tier in (ConfidenceTier.INDEPENDENTLY_CORROBORATED, ConfidenceTier.PRIMARY_CONFIRMED)
    assert top_fact.independent_source_count >= 2


def test_continuous_tier_promotion_tier2_to_tier1(cont_env, tmp_path):
    engine, pipeline, storage, registry = cont_env

    # 1. Ingest secondary reporting
    item_1, _, claims_1 = pipeline.process_raw_item(
        source_id="reuters",
        url="https://reuters.com/report-1",
        title="Preliminary Casualty Estimates",
        raw_text="Six maintenance workers died in the catastrophic bridge collapse.",
        custom_id="it-reuters-casualties",
    )
    engine.update_event_with_item("ev-casualties", item_1, claims_1, output_dir=tmp_path / "briefs")

    # 2. Ingest Primary official agency report (NTSB)
    item_prim, _, claims_prim = pipeline.process_raw_item(
        source_id="ntsb-gov",
        url="https://ntsb.gov/investigations/1",
        title="NTSB Formal Accident Report",
        raw_text="The NTSB confirmed six maintenance workers died in the bridge collapse.",
        custom_id="it-ntsb-report",
    )
    _, brief_updated, diff = engine.update_event_with_item(
        event_id="ev-casualties",
        item=item_prim,
        claims=claims_prim,
        output_dir=tmp_path / "briefs",
    )

    # Must be promoted to Tier 1 Primary Confirmed
    assert len(brief_updated.core_facts) >= 1
    assert brief_updated.core_facts[0].tier == ConfidenceTier.PRIMARY_CONFIRMED
    assert "ntsb-gov" in brief_updated.core_facts[0].supporting_source_ids


def test_continuous_retraction_propagation(cont_env, tmp_path):
    engine, pipeline, storage, registry = cont_env

    # 1. Ingest single source story
    item, _, claims = pipeline.process_raw_item(
        source_id="reuters",
        url="https://reuters.com/fake-story",
        title="Unverified Rumor Report",
        raw_text="Investigators discovered explosive residue on the bridge piers.",
        custom_id="it-retracted-01",
    )
    event, brief, _ = engine.update_event_with_item("ev-retraction-test", item, claims, output_dir=tmp_path / "briefs")
    assert len(event.claim_ids) >= 1

    # 2. Publisher issues retraction
    results = engine.handle_retraction(
        item_id="it-retracted-01",
        reason="Source fabricated claim; fully retracted by publisher.",
        output_dir=tmp_path / "briefs",
    )

    assert len(results) == 1
    ev_res, brief_res, diff_res = results[0]
    assert "it-retracted-01" in diff_res.summary_of_changes
    # All claims for item should now be rejected
    retracted_claim = storage.get_claim(claims[0].id)
    assert retracted_claim.status == ClaimStatus.REJECTED
