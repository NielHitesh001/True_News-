"""Tests for M0 Gold Set and Agreement Calculation."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from newsx.schemas import (
    GoldArticleLabel,
    GoldClaimLabel,
    GoldEventGroup,
    GoldPassageLabel,
)
from scripts.calculate_agreement import main as run_agreement_calculation

ROOT = Path(__file__).resolve().parent.parent


def test_gold_raw_items_exist_and_valid():
    raw_path = ROOT / "gold" / "raw" / "items.jsonl"
    assert raw_path.exists(), "gold/raw/items.jsonl does not exist"

    with raw_path.open("r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    assert len(items) == 12, f"Expected 12 raw items, got {len(items)}"
    event_kinds = {item["event_kind"] for item in items}
    assert event_kinds == {"hard-fact", "numeric", "contested"}


def test_gold_labels_schema_compliance():
    for pass_id in ["pass_a", "pass_b"]:
        pass_dir = ROOT / "gold" / "labels" / pass_id

        # Articles
        with (pass_dir / "articles.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                GoldArticleLabel(**rec)

        # Passages
        with (pass_dir / "passages.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                GoldPassageLabel(**rec)

        # Claims
        with (pass_dir / "claims.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                GoldClaimLabel(**rec)

        # Events
        with (pass_dir / "events.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                GoldEventGroup(**rec)


def test_agreement_metrics_thresholds():
    metrics = run_agreement_calculation()

    # Article Cohen's Kappa >= 0.75
    assert metrics["article_type"]["cohens_kappa"] >= 0.75, (
        f"Article kappa {metrics['article_type']['cohens_kappa']} < 0.75"
    )

    # Passage Cohen's Kappa >= 0.75
    assert metrics["passage_type"]["cohens_kappa"] >= 0.75, (
        f"Passage kappa {metrics['passage_type']['cohens_kappa']} < 0.75"
    )

    # Feeds fact base Cohen's Kappa >= 0.75
    assert metrics["feeds_fact_base"]["cohens_kappa"] >= 0.75, (
        f"Feeds fact base kappa {metrics['feeds_fact_base']['cohens_kappa']} < 0.75"
    )

    # Claim Span F1 >= 0.85
    assert metrics["claim_spans"]["f1"] >= 0.85, (
        f"Claim span F1 {metrics['claim_spans']['f1']} < 0.85"
    )
