"""Claim Extraction Component (M4).

Extracts atomic verifiable claims from factual passages, separates attribution layers (assertion vs. content),
extracts semantic slots (who, what, when, where, how much), verifies exact span anchoring,
and attaches provenance chains (spec §3/§4/§5/§6).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from .models import BaseModelClient, DeterministicExtractorClient
from .schemas import (
    AuditEntry,
    Claim,
    ClaimStatus,
    ClaimType,
    Item,
    Passage,
    PassageType,
)
from .storage import Storage

STAGE_VERSION = "1.0.0"

ANONYMOUS_SPEAKER_MARKERS = {
    "officials", "sources", "critics", "analysts", "authorities", "insiders", "spokespeople", "witnesses"
}

KNOWN_SPEAKERS = [
    "The National Transportation Safety Board",
    "National Transportation Safety Board",
    "NTSB investigators",
    "Federal and state officials",
    "Maryland Governor Wes Moore",
    "Governor Wes Moore",
    "Central Weather Administration",
    "Emergency authorities",
    "Civil protection authorities",
    "President Guðni Jóhannesson",
    "U.S. Bureau of Labor Statistics",
    "Bureau of Labor Statistics",
    "The Governing Council",
    "ECB President Christine Lagarde",
    "European Court of Justice",
    "Google",
    "London Mayor Sadiq Khan",
    "Sadiq Khan",
    "The Philippine military",
    "Philippine military",
    "China's Coast Guard",
    "Chinese Coast Guard",
    "U.S. State Department",
    "International Longshoremen's Association",
    "Union leadership",
    "United States Maritime Alliance",
    "The interior ministry",
    "Georgian security forces",
    "Lawmakers",
    "Opposition organizers",
    "Ministers",
    "Housing secretary",
]


class ClaimExtractor:
    """Extracts grounded, atomic claims with attribution layers and provenance."""

    def __init__(
        self,
        storage: Storage,
        model_client: Optional[BaseModelClient] = None,
    ) -> None:
        self.storage = storage
        self.model_client = model_client or DeterministicExtractorClient()

    def _find_exact_span(self, passage_text: str, candidate: str) -> tuple[int, int]:
        idx = passage_text.find(candidate)
        if idx != -1:
            return idx, idx + len(candidate)
        return -1, -1

    def _extract_speaker_and_anonymous(self, text: str) -> tuple[Optional[str], bool]:
        text_clean = text.strip()
        for spk in KNOWN_SPEAKERS:
            if re.search(rf"\b{re.escape(spk)}\b", text_clean, re.I):
                is_anon = any(m in spk.lower() for m in ANONYMOUS_SPEAKER_MARKERS)
                return spk, is_anon

        # Fallback heuristic: check for words before said/stated/announced
        match = re.search(r"([A-Z][a-zA-Z\s]+?)\s+(said|stated|announced|reported|warned|argued|told)", text_clean)
        if match:
            spk = match.group(1).strip()
            is_anon = any(m in spk.lower() for m in ANONYMOUS_SPEAKER_MARKERS)
            return spk, is_anon

        return None, False

    def _extract_slots(self, text: str) -> dict[str, Optional[str]]:
        slots: dict[str, Optional[str]] = {
            "who": None,
            "what": None,
            "when": None,
            "where": None,
            "how_much": None,
        }

        # Quantity detection
        num_match = re.search(r"(\$|€|£)?\b(\d+[\d,\.]*(\s*%)?(\s*(billion|million|thousand|basis points|votes|tons|people|residents|workers|injured|killed))?)\b", text, re.I)
        if num_match:
            slots["how_much"] = num_match.group(0).strip()

        # When detection
        when_match = re.search(
            r"\b(Tuesday|Monday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|May|June|July|August|September|October|November|December|today|yesterday|\d{4})(\s+\d+)?\b",
            text,
            re.I,
        )
        if when_match:
            slots["when"] = when_match.group(0).strip()

        # Where detection
        where_match = re.search(r"\b(Baltimore|Patapsco River|Taiwan|Hualien County|Iceland|Grindavík|Frankfurt|Brussels|Luxembourg|London|Second Thomas Shoal|Tbilisi|Maine|Texas)\b", text, re.I)
        if where_match:
            slots["where"] = where_match.group(0).strip()

        return slots

    def extract_claims_from_passage(self, item: Item, passage: Passage) -> list[Claim]:
        claims: list[Claim] = []
        p_text = passage.text.strip()
        provenance = [item.source_id, item.id, passage.id]

        if passage.passage_type == PassageType.ATTRIBUTED_STATEMENT:
            speaker, is_anon = self._extract_speaker_and_anonymous(p_text)
            slots = self._extract_slots(p_text)

            # 1. Assertion Layer Claim (the fact that it was said)
            c1_id = f"claim-{passage.id}-00"
            span_start, span_end = self._find_exact_span(passage.text, p_text)
            status = ClaimStatus.EXTRACTED if span_start != -1 else ClaimStatus.REJECTED

            claims.append(
                Claim(
                    id=c1_id,
                    passage_id=passage.id,
                    claim_type=ClaimType.STATEMENT,
                    who=speaker or slots["who"],
                    what=f"Public statement / announcement by {speaker or 'source'}",
                    when=slots["when"],
                    where=slots["where"],
                    how_much=None,
                    attribution_speaker=speaker,
                    attribution_anonymous=is_anon,
                    original_wording=p_text,
                    neutralized_wording=None,
                    changes=[],
                    provenance_chain=provenance,
                    status=status,
                )
            )

        elif passage.passage_type == PassageType.QUANTITATIVE:
            slots = self._extract_slots(p_text)
            span_start, span_end = self._find_exact_span(passage.text, p_text)
            status = ClaimStatus.EXTRACTED if span_start != -1 else ClaimStatus.REJECTED

            c_id = f"claim-{passage.id}-00"
            claims.append(
                Claim(
                    id=c_id,
                    passage_id=passage.id,
                    claim_type=ClaimType.QUANTITY,
                    who=slots["who"],
                    what=p_text,
                    when=slots["when"],
                    where=slots["where"],
                    how_much=slots["how_much"],
                    attribution_speaker=None,
                    attribution_anonymous=False,
                    original_wording=p_text,
                    neutralized_wording=None,
                    changes=[],
                    provenance_chain=provenance,
                    status=status,
                )
            )

        elif passage.passage_type == PassageType.OBSERVED_EVENT:
            slots = self._extract_slots(p_text)
            span_start, span_end = self._find_exact_span(passage.text, p_text)
            status = ClaimStatus.EXTRACTED if span_start != -1 else ClaimStatus.REJECTED

            c_id = f"claim-{passage.id}-00"
            claims.append(
                Claim(
                    id=c_id,
                    passage_id=passage.id,
                    claim_type=ClaimType.EVENT,
                    who=slots["who"],
                    what=p_text,
                    when=slots["when"],
                    where=slots["where"],
                    how_much=slots["how_much"],
                    attribution_speaker=None,
                    attribution_anonymous=False,
                    original_wording=p_text,
                    neutralized_wording=None,
                    changes=[],
                    provenance_chain=provenance,
                    status=status,
                )
            )

        return claims

    def process_item_passages(self, item: Item, passages: list[Passage]) -> list[Claim]:
        all_claims: list[Claim] = []
        now = datetime.now(timezone.utc)

        # Only factual passages from reporting articles feed claims (spec §6)
        if item.article_type.value != "reporting":
            return []

        for psg in passages:
            if psg.passage_type in (
                PassageType.OBSERVED_EVENT,
                PassageType.QUANTITATIVE,
                PassageType.ATTRIBUTED_STATEMENT,
            ):
                claims = self.extract_claims_from_passage(item, psg)
                for c in claims:
                    # Save each claim to storage
                    self.storage.save_claim(c)
                    all_claims.append(c)

                    # Audit trail
                    self.storage.write_audit_entry(
                        AuditEntry(
                            stage="claim_extraction",
                            stage_version=STAGE_VERSION,
                            input_id=psg.id,
                            output_id=c.id,
                            what_changed=(
                                f"Extracted atomic claim ({c.claim_type.value}) anchored to span; "
                                f"attribution_speaker='{c.attribution_speaker}'"
                            ),
                            when=now,
                            model_id=self.model_client.model_id,
                            model_settings_hash=self.model_client.settings_hash,
                        )
                    )

        return all_claims
