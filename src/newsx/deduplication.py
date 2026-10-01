"""Deduplication and Syndication Tracker (M2).

Identifies exact duplicates and syndicated/republished wire copy.
Maintains links to duplicates or republished-from items without double-counting origins (spec §3.5/§5).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from .schemas import AuditEntry, Item
from .storage import Storage

STAGE_VERSION = "1.0.0"


def tokenize_text(text: str) -> set[str]:
    """Extract normalized word n-grams for Jaccard similarity comparison."""
    words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
    if len(words) < 3:
        return set(words)
    # Generate 3-grams
    return {" ".join(words[i : i + 3]) for i in range(len(words) - 2)}


def calculate_jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


class Deduplicator:
    """Detects duplicates and syndicated republishing across ingested items."""

    def __init__(
        self,
        storage: Storage,
        exact_threshold: float = 0.95,
        republish_threshold: float = 0.70,
    ) -> None:
        self.storage = storage
        self.exact_threshold = exact_threshold
        self.republish_threshold = republish_threshold

    def process_item(self, item: Item, existing_items: Optional[list[Item]] = None) -> Item:
        candidates = existing_items if existing_items is not None else self.storage.list_items()
        candidates = [c for c in candidates if c.id != item.id]

        if not candidates or not item.cleaned_text.strip():
            return item

        target_ngrams = tokenize_text(item.cleaned_text)
        if not target_ngrams:
            return item

        best_match: Optional[Item] = None
        best_sim = 0.0

        for candidate in candidates:
            if not candidate.cleaned_text.strip():
                continue
            cand_ngrams = tokenize_text(candidate.cleaned_text)
            sim = calculate_jaccard_similarity(target_ngrams, cand_ngrams)
            if sim > best_sim:
                best_sim = sim
                best_match = candidate

        changed = False
        now = datetime.now(timezone.utc)

        if best_match and best_sim >= self.exact_threshold:
            item.duplicate_of = best_match.id
            changed = True
            self.storage.write_audit_entry(
                AuditEntry(
                    stage="deduplication",
                    stage_version=STAGE_VERSION,
                    input_id=item.id,
                    output_id=best_match.id,
                    what_changed=f"Marked as exact duplicate of {best_match.id} (similarity: {best_sim:.3f})",
                    when=now,
                )
            )
        elif best_match and best_sim >= self.republish_threshold:
            item.republished_from = best_match.id
            changed = True
            self.storage.write_audit_entry(
                AuditEntry(
                    stage="deduplication",
                    stage_version=STAGE_VERSION,
                    input_id=item.id,
                    output_id=best_match.id,
                    what_changed=f"Marked as republished from {best_match.id} (similarity: {best_sim:.3f})",
                    when=now,
                )
            )

        if changed:
            self.storage.save_item(item)

        return item
