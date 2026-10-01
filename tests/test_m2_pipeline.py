"""Integration tests for M2 End-to-End Pipeline."""

from __future__ import annotations

from pathlib import Path
import pytest

from newsx.pipeline import Pipeline
from newsx.registry import SourceRegistry
from newsx.storage import Storage

ROOT = Path(__file__).resolve().parent.parent


def test_pipeline_run_event(tmp_path):
    db_file = tmp_path / "test_newsx.db"
    audit_file = tmp_path / "test_audit.jsonl"
    raw_dir = tmp_path / "raw"

    storage = Storage(db_path=db_file, audit_path=audit_file)
    registry = SourceRegistry()
    pipeline = Pipeline(storage=storage, registry=registry)
    pipeline.collector.raw_dir = raw_dir

    # Run on gold event 'event-key-bridge-01'
    event = pipeline.run_event_from_gold_file("event-key-bridge-01")

    assert event.id == "event-key-bridge-01"
    assert len(event.member_item_ids) == 2  # gold-art-001 (NTSB) and gold-art-002 (AP)

    # Check database items
    item_1 = storage.get_item("gold-art-001")
    assert item_1 is not None
    assert item_1.source_id == "ntsb-gov"

    psgs_1 = storage.get_passages_for_item("gold-art-001")
    assert len(psgs_1) == 4

    item_2 = storage.get_item("gold-art-002")
    assert item_2 is not None
    assert item_2.source_id == "ap-news"

    psgs_2 = storage.get_passages_for_item("gold-art-002")
    assert len(psgs_2) == 4

    # Check audit log written
    assert audit_file.exists()
    audit_lines = audit_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(audit_lines) >= 4  # collection + normalization + event assembly


def test_pipeline_run_all_gold_events(tmp_path):
    storage = Storage(db_path=tmp_path / "test_newsx.db", audit_path=tmp_path / "test_audit.jsonl")
    registry = SourceRegistry()
    pipeline = Pipeline(storage=storage, registry=registry)

    event = pipeline.run_event_from_gold_file("all")
    assert len(event.member_item_ids) == 12

    stored_items = storage.list_items()
    assert len(stored_items) == 12
