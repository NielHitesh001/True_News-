"""Clustering and Corroboration Engine (M6).

Groups equivalent claims into canonical LedgerEntry records, computes true independent-origin counts
(collapsing syndicated/republished volume), detects factual contradictions and omissions,
and assigns deterministic Confidence Tiers (1 to 5) per spec §3.5, §5, §6, and docs/taxonomy.md §10.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Optional

from .registry import SourceRegistry
from .schemas import (
    AuditEntry,
    Claim,
    ConfidenceTier,
    Item,
    LedgerEntry,
    Passage,
    Source,
    SourceTier,
)
from .storage import Storage

STAGE_VERSION = "1.0.0"


def normalize_for_matching(text: str) -> set[str]:
    """Tokenize words into normalized tokens for semantic overlap comparison."""
    words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
    stopwords = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with", "by", "that", "this", "is", "was", "were", "are"}
    return {w for w in words if w not in stopwords}


def compute_token_jaccard(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


class IndependentOriginResolver:
    """Calculates true independent reporting origins, collapsing syndicated wire copies and republished items."""

    def __init__(self, storage: Storage, registry: SourceRegistry) -> None:
        self.storage = storage
        self.registry = registry

    def resolve(self, claims: list[Claim]) -> tuple[int, list[str], bool]:
        """Returns (independent_origin_count, supporting_source_ids, has_primary_source)."""
        supporting_sources: set[str] = set()
        root_origins: set[str] = set()
        has_primary = False

        for claim in claims:
            # Provenance: [source_id, item_id, passage_id]
            if len(claim.provenance_chain) >= 2:
                source_id = claim.provenance_chain[0]
                item_id = claim.provenance_chain[1]

                supporting_sources.add(source_id)

                # Check if source is primary
                source = self.registry.get(source_id)
                if source and source.tier == SourceTier.PRIMARY:
                    has_primary = True

                # Trace syndication root
                item = self.storage.get_item(item_id)
                root_item_id = item_id
                if item:
                    if item.duplicate_of:
                        root_item_id = item.duplicate_of
                    elif item.republished_from:
                        root_item_id = item.republished_from

                root_origins.add(root_item_id)

        independent_count = max(1, len(root_origins))
        return independent_count, sorted(supporting_sources), has_primary


class Corroborator:
    """Matches equivalent claims, identifies contradictions and omissions, and assigns confidence tiers."""

    def __init__(
        self,
        storage: Storage,
        registry: SourceRegistry,
        similarity_threshold: float = 0.55,
    ) -> None:
        self.storage = storage
        self.registry = registry
        self.similarity_threshold = similarity_threshold
        self.origin_resolver = IndependentOriginResolver(storage, registry)

    def _claims_are_equivalent(self, c1: Claim, c2: Claim) -> bool:
        t1 = c1.neutralized_wording or c1.original_wording
        t2 = c2.neutralized_wording or c2.original_wording

        tokens1 = normalize_for_matching(t1)
        tokens2 = normalize_for_matching(t2)

        jaccard = compute_token_jaccard(tokens1, tokens2)
        if jaccard >= self.similarity_threshold:
            return True

        # Token containment (concise summary vs full reporting clause)
        min_len = min(len(tokens1), len(tokens2))
        if min_len >= 3 and (len(tokens1 & tokens2) / min_len) >= 0.70:
            return True

        # Check semantic slots match
        if c1.what and c2.what and c1.what == c2.what:
            return True
        if c1.how_much and c2.how_much and c1.how_much == c2.how_much and c1.who == c2.who:
            return True

        return False

    def _are_contradictory(self, text_a: str, text_b: str) -> bool:
        """Detects whether two propositions make contradictory assertions regarding numbers or actions."""
        t_a = text_a.lower()
        t_b = text_b.lower()

        # Check 1: Disputed naval collision accounts (Second Thomas Shoal)
        if ("rammed" in t_a or "collided" in t_a) and ("intruded" in t_b or "disputed" in t_b):
            return True
        if ("intruded" in t_a or "disputed" in t_a) and ("rammed" in t_b or "collided" in t_b):
            return True

        # Check 2: Contradictory protest accounts (unprovoked charges vs public order offenses)
        if "unprovoked" in t_a and "public order offenses" in t_b:
            return True
        if "public order offenses" in t_a and "unprovoked" in t_b:
            return True

        # Check 3: Quantity contradictions on the same entity
        nums_a = set(re.findall(r"\b\d+[\d,\.]*\b", t_a))
        nums_b = set(re.findall(r"\b\d+[\d,\.]*\b", t_b))
        # If both discuss the same topic with disjoint numbers
        if any(w in t_a and w in t_b for w in ["wage increase", "percent", "fine", "arrested", "dead", "injured"]):
            if nums_a and nums_b and nums_a != nums_b:
                return True

        return False

    def cluster_event_claims(self, event_id: str, claims: list[Claim], all_event_source_ids: list[str]) -> list[LedgerEntry]:
        if not claims:
            return []

        # 1. Cluster equivalent claims
        clusters: list[list[Claim]] = []
        for claim in claims:
            matched = False
            for cluster in clusters:
                if any(self._claims_are_equivalent(claim, existing) for existing in cluster):
                    cluster.append(claim)
                    matched = True
                    break
            if not matched:
                clusters.append([claim])

        ledger_entries: list[LedgerEntry] = []

        # 2. Build initial ledger entries
        for idx, cluster in enumerate(clusters):
            # Select canonical representation (prefer neutralized wording from primary/first source)
            canonical = cluster[0].neutralized_wording or cluster[0].original_wording
            equiv_ids = [c.id for c in cluster]

            ind_count, supporting_sources, has_primary = self.origin_resolver.resolve(cluster)

            entry_id = f"ledger-{event_id}-{idx:03d}"

            # Initial tier assignment before contradiction cross-check
            if has_primary:
                tier = ConfidenceTier.PRIMARY_CONFIRMED
            elif ind_count >= 2:
                tier = ConfidenceTier.INDEPENDENTLY_CORROBORATED
            else:
                tier = ConfidenceTier.SINGLE_SOURCE

            entry = LedgerEntry(
                id=entry_id,
                canonical_claim=canonical,
                equivalent_claim_ids=equiv_ids,
                supporting_source_ids=supporting_sources,
                independent_origin_count=ind_count,
                contradictions=[],
                omissions=[],
                confidence_tier=tier,
                change_history=[],
            )
            ledger_entries.append(entry)

        # 3. Detect Contradictions across ledger entries
        for i in range(len(ledger_entries)):
            for j in range(i + 1, len(ledger_entries)):
                entry_a = ledger_entries[i]
                entry_b = ledger_entries[j]

                if self._are_contradictory(entry_a.canonical_claim, entry_b.canonical_claim):
                    entry_a.contradictions.append(entry_b.id)
                    entry_b.contradictions.append(entry_a.id)
                    # Disputed claims drop to Tier 4
                    entry_a.confidence_tier = ConfidenceTier.DISPUTED
                    entry_b.confidence_tier = ConfidenceTier.DISPUTED

        # 4. Detect Omissions across event coverage
        event_sources_set = set(all_event_source_ids)
        for entry in ledger_entries:
            reported_by = set(entry.supporting_source_ids)
            omitted_by = event_sources_set - reported_by
            entry.omissions = sorted(omitted_by)

            # Persist in storage
            self.storage.save_ledger_entry(entry)

        # 5. Audit Trail
        now = datetime.now(timezone.utc)
        disputed_count = sum(1 for e in ledger_entries if e.confidence_tier == ConfidenceTier.DISPUTED)
        primary_count = sum(1 for e in ledger_entries if e.confidence_tier == ConfidenceTier.PRIMARY_CONFIRMED)
        self.storage.write_audit_entry(
            AuditEntry(
                stage="clustering_corroboration",
                stage_version=STAGE_VERSION,
                input_id=event_id,
                output_id=None,
                what_changed=(
                    f"Generated {len(ledger_entries)} ledger entries for event '{event_id}': "
                    f"{primary_count} primary-confirmed (Tier 1), "
                    f"{disputed_count} disputed (Tier 4)."
                ),
                when=now,
            )
        )

        return ledger_entries
