"""Unit tests for Neutralizer Engine and Meaning Preservation (M5)."""

from __future__ import annotations

import pytest
from newsx.neutralizer import MeaningChecker, Neutralizer
from newsx.schemas import ChangeRecord, Claim, ClaimStatus, ClaimType
from newsx.storage import Storage


@pytest.fixture
def neutralizer(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db", audit_path=tmp_path / "audit.jsonl")
    return Neutralizer(storage)


def test_neutralizer_intensifier_removal(neutralizer):
    claim = Claim(
        id="c-test-1",
        passage_id="p-1",
        claim_type=ClaimType.QUANTITY,
        original_wording="The regulator imposed a staggering $2 billion fine.",
        provenance_chain=["src", "item", "p-1"],
    )
    res = neutralizer.neutralize_claim(claim)
    assert res.status == ClaimStatus.NEUTRALIZED
    assert res.neutralized_wording == "The regulator imposed a $2 billion fine."
    assert len(res.changes) == 1
    assert res.changes[0].original_span == "staggering"
    assert res.changes[0].category == "intensifier"


def test_neutralizer_charged_verb_replacement(neutralizer):
    claim = Claim(
        id="c-test-2",
        passage_id="p-1",
        claim_type=ClaimType.EVENT,
        original_wording="The senator slammed the proposed energy bill on Tuesday.",
        provenance_chain=["src", "item", "p-1"],
    )
    res = neutralizer.neutralize_claim(claim)
    assert res.status == ClaimStatus.NEUTRALIZED
    assert "criticized" in res.neutralized_wording
    assert "slammed" not in res.neutralized_wording
    assert res.changes[0].category == "charged_verb"


def test_neutralizer_scare_quotes_stripping(neutralizer):
    claim = Claim(
        id="c-test-3",
        passage_id="p-1",
        claim_type=ClaimType.EVENT,
        original_wording="The 'so-called independent' board approved the budget.",
        provenance_chain=["src", "item", "p-1"],
    )
    res = neutralizer.neutralize_claim(claim)
    assert res.status == ClaimStatus.NEUTRALIZED
    assert res.neutralized_wording == "The independent board approved the budget."
    assert res.changes[0].category == "loaded_label"


def test_neutralizer_factual_whitelist_preservation(neutralizer):
    # 'hospitalized', 'injured', 'killed' must NOT be removed (spec §6)
    claim = Claim(
        id="c-test-4",
        passage_id="p-1",
        claim_type=ClaimType.EVENT,
        original_wording="Three protesters were hospitalized after the clash.",
        provenance_chain=["src", "item", "p-1"],
    )
    res = neutralizer.neutralize_claim(claim)
    assert "hospitalized" in res.neutralized_wording
    assert res.status == ClaimStatus.NEUTRALIZED


def test_meaning_checker_missing_number_fails():
    checker = MeaningChecker(whitelist=["hospitalized", "injured"])
    # If candidate rewrite dropped the number $2 billion
    orig = "The regulator fined the company $2 billion."
    bad_neut = "The regulator fined the company."

    passed, reason = checker.verify(orig, bad_neut)
    assert passed is False
    assert "Missing factual numbers" in reason


def test_meaning_checker_missing_whitelist_fails():
    checker = MeaningChecker(whitelist=["hospitalized", "injured"])
    orig = "Three officers were hospitalized."
    bad_neut = "Three officers were present."

    passed, reason = checker.verify(orig, bad_neut)
    assert passed is False
    assert "hospitalized" in reason
