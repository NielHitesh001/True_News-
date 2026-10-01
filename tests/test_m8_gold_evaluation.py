"""Test suite for Milestone 8 (Continuous & Multi-Event Pipeline)."""

from __future__ import annotations

from newsx.continuous import ContinuousEngine, EventMatcher
from newsx.pipeline import Pipeline
from newsx.registry import SourceRegistry
from newsx.schemas import ClaimStatus, ConfidenceTier
from newsx.storage import Storage


def test_m8_continuous_lifecycle_gold_benchmark(tmp_path):
    storage = Storage(db_path=tmp_path / "m8.db", audit_path=tmp_path / "m8_audit.jsonl")
    registry = SourceRegistry()
    for s in registry.all_sources():
        storage.save_source(s)

    pipeline = Pipeline(storage, registry)
    engine = ContinuousEngine(storage, registry)
    matcher = EventMatcher(storage)
    out_dir = tmp_path / "briefs"

    # 1. Wave 1: First item
    it1, _, cl1 = pipeline.process_raw_item(
        source_id="reuters",
        url="https://reuters.com/b1",
        title="Dali strikes Key Bridge in Baltimore",
        raw_text="The container ship Dali struck the Francis Scott Key Bridge early Tuesday morning.\nSix workers are missing.",
        custom_id="m8-it-1",
    )
    ev, b1, d1 = engine.update_event_with_item("m8-ev-bridge", it1, cl1, output_dir=out_dir)
    assert len(ev.member_item_ids) == 1

    # 2. Wave 2: Matching & Second item (Tier 3 -> Tier 2)
    it2, _, cl2 = pipeline.process_raw_item(
        source_id="ap-news",
        url="https://apnews.com/b2",
        title="Key Bridge salvage continues as six workers missing",
        raw_text="Emergency responders confirmed six road workers were missing following the Dali bridge strike on Tuesday.",
        custom_id="m8-it-2",
    )
    matched = matcher.match_event(it2.title, it2.cleaned_text)
    assert matched == "m8-ev-bridge"

    ev2, b2, d2 = engine.update_event_with_item("m8-ev-bridge", it2, cl2, output_dir=out_dir)
    assert len(ev2.member_item_ids) == 2
    assert any(f.tier in (ConfidenceTier.INDEPENDENTLY_CORROBORATED, ConfidenceTier.PRIMARY_CONFIRMED) for f in b2.core_facts)

    # 3. Wave 3: Primary report (Tier 2 -> Tier 1)
    it3, _, cl3 = pipeline.process_raw_item(
        source_id="ntsb-gov",
        url="https://ntsb.gov/b3",
        title="NTSB Preliminary Report",
        raw_text="The NTSB confirmed six road workers died in the Francis Scott Key Bridge collapse.",
        custom_id="m8-it-3",
    )
    ev3, b3, d3 = engine.update_event_with_item("m8-ev-bridge", it3, cl3, output_dir=out_dir)
    assert any(f.tier == ConfidenceTier.PRIMARY_CONFIRMED for f in b3.core_facts)

    # 4. Wave 4: Retraction handling
    it_err, _, cl_err = pipeline.process_raw_item(
        source_id="the-guardian",
        url="https://guardian.com/bad",
        title="Retracted story",
        raw_text="Unverified rumor about sensor fault on bridge.",
        custom_id="m8-it-err",
    )
    engine.update_event_with_item("m8-ev-bridge", it_err, cl_err, output_dir=out_dir)
    retractions = engine.handle_retraction("m8-it-err", reason="Unverified rumor", output_dir=out_dir)
    assert len(retractions) == 1
    assert storage.get_claim(cl_err[0].id).status == ClaimStatus.REJECTED
