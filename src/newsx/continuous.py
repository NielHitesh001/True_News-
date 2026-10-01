"""Continuous & Multi-Event Pipeline Engine (Milestone 8).

Handles dynamic event matching, incremental article ingestion, confidence tier transitions,
publisher retraction propagation, brief versioning, and structured diff generation.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from newsx.brief import BriefGenerator
from newsx.corroboration import Corroborator
from newsx.presenter import HtmlBriefRenderer, MarkdownBriefRenderer
from newsx.registry import DiversityChecker, SourceRegistry
from newsx.schemas import (
    ArticleType,
    AuditEntry,
    Brief,
    BriefDiff,
    BriefFact,
    Claim,
    ClaimStatus,
    ConfidenceTier,
    DisputedPoint,
    Event,
    Item,
    Passage,
)
from newsx.storage import Storage

STAGE_VERSION = "1.0.0"


class EventMatcher:
    """Matches new incoming articles to existing active events via entity and token overlap."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def _tokenize(self, text: str) -> set[str]:
        words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
        stopwords = {
            "the", "and", "for", "that", "this", "with", "from", "have", "were",
            "said", "will", "been", "after", "reported", "statement", "official",
        }
        return set(w for w in words if w not in stopwords)

    def match_event(self, item_title: str, item_text: str, candidate_event_ids: Optional[list[str]] = None) -> Optional[str]:
        """Finds the best matching active event for a given new article text."""
        new_tokens = self._tokenize(f"{item_title} {item_text[:500]}")
        if not new_tokens:
            return None

        best_event_id: Optional[str] = None
        best_score = 0.0

        # Look up events in storage
        event_ids = candidate_event_ids
        if event_ids is None:
            # Gather all stored event records
            with self.storage._get_connection() as conn:
                rows = conn.execute("SELECT id FROM events").fetchall()
                event_ids = [r["id"] for r in rows]

        for ev_id in event_ids:
            event = self.storage.get_event(ev_id)
            if not event or not event.member_item_ids:
                continue

            # Gather event text
            event_text_parts = [event.label]
            for it_id in event.member_item_ids[:3]:
                it = self.storage.get_item(it_id)
                if it:
                    event_text_parts.append(it.title)
                    event_text_parts.append(it.cleaned_text[:300])

            ev_tokens = self._tokenize(" ".join(event_text_parts))
            if not ev_tokens:
                continue

            intersection = len(new_tokens & ev_tokens)
            union = len(new_tokens | ev_tokens)
            score = intersection / union if union > 0 else 0.0

            if score > best_score and score >= 0.15:  # threshold for event matching
                best_score = score
                best_event_id = ev_id

        return best_event_id


class ContinuousEngine:
    """Orchestrates incremental updates, tier evolutions, retractions, and brief diffs."""

    def __init__(
        self,
        storage: Optional[Storage] = None,
        registry: Optional[SourceRegistry] = None,
    ) -> None:
        self.storage = storage or Storage()
        self.registry = registry or SourceRegistry()
        self.diversity_checker = DiversityChecker(self.registry)
        self.corroborator = Corroborator(self.storage, self.registry)
        self.brief_generator = BriefGenerator(self.storage, self.registry, self.diversity_checker)
        self.matcher = EventMatcher(self.storage)
        self._brief_cache: dict[str, Brief] = {}

    def compute_brief_diff(
        self,
        prev_brief: Optional[Brief],
        new_brief: Brief,
        prev_version: str = "v1.0.0",
        new_version: str = "v1.1.0",
    ) -> BriefDiff:
        """Computes a structured diff between two versions of an event brief."""
        if prev_brief is None:
            return BriefDiff(
                event_id=new_brief.event_id,
                previous_version="none",
                current_version=new_version,
                new_core_facts=[f.text for f in new_brief.core_facts if f.text],
                promoted_facts=[],
                new_disputes=[
                    dp.topic if isinstance(dp, DisputedPoint) else str(dp)
                    for dp in new_brief.disputed_points
                ],
                retracted_claims=[],
                summary_of_changes=f"Initial brief created with {len(new_brief.core_facts)} core facts.",
            )

        prev_fact_map = {f.claim_id: f for f in prev_brief.core_facts}
        new_fact_map = {f.claim_id: f for f in new_brief.core_facts}

        new_core: list[str] = []
        promoted: list[str] = []

        for cid, new_fact in new_fact_map.items():
            if cid not in prev_fact_map:
                # Check if it was single source previously
                prev_single = next((f for f in prev_brief.single_source_facts if f.claim_id == cid), None)
                if prev_single:
                    promoted.append(f"Promoted from Tier 3 to Tier 2: {new_fact.text}")
                else:
                    new_core.append(new_fact.text or "")
            else:
                prev_f = prev_fact_map[cid]
                if prev_f.tier != new_fact.tier:
                    promoted.append(f"Tier transition ({prev_f.tier.value} -> {new_fact.tier.value}): {new_fact.text}")

        # Check disputes
        prev_disputes = {
            dp.topic if isinstance(dp, DisputedPoint) else str(dp)
            for dp in prev_brief.disputed_points
        }
        new_disputes = [
            dp.topic if isinstance(dp, DisputedPoint) else str(dp)
            for dp in new_brief.disputed_points
            if (dp.topic if isinstance(dp, DisputedPoint) else str(dp)) not in prev_disputes
        ]

        summary_parts = []
        if new_core:
            summary_parts.append(f"+{len(new_core)} new core facts")
        if promoted:
            summary_parts.append(f"{len(promoted)} confidence tier upgrades")
        if new_disputes:
            summary_parts.append(f"+{len(new_disputes)} new disputed points")

        summary = ", ".join(summary_parts) if summary_parts else "No material factual changes"

        return BriefDiff(
            event_id=new_brief.event_id,
            previous_version=prev_version,
            current_version=new_version,
            new_core_facts=new_core,
            promoted_facts=promoted,
            new_disputes=new_disputes,
            retracted_claims=[],
            summary_of_changes=summary,
        )

    def update_event_with_item(
        self,
        event_id: str,
        item: Item,
        claims: list[Claim],
        event_category: str = "hard_fact",
        output_dir: Optional[Path] = None,
    ) -> tuple[Event, Brief, BriefDiff]:
        """Incorporates a newly processed item and its claims into an existing event, updating briefs."""
        event = self.storage.get_event(event_id)
        if not event:
            event = Event(
                id=event_id,
                label=item.title,
                member_item_ids=[item.id],
                time_span=(item.published_time, item.published_time),
                claim_ids=[c.id for c in claims],
            )
        else:
            if item.id not in event.member_item_ids:
                event.member_item_ids.append(item.id)
            for c in claims:
                if c.id not in event.claim_ids:
                    event.claim_ids.append(c.id)

        self.storage.save_event(event)

        # Retrieve previous brief from cache or generate baseline
        prev_brief = self._brief_cache.get(event_id)

        # Collect all claims for event
        all_event_claims: list[Claim] = []
        for cid in event.claim_ids:
            c = self.storage.get_claim(cid)
            if c and c.status != ClaimStatus.REJECTED:
                all_event_claims.append(c)

        # Re-corroborate
        member_items = [self.storage.get_item(iid) for iid in event.member_item_ids]
        valid_items = [it for it in member_items if it is not None]
        source_ids = sorted(list(set(it.source_id for it in valid_items)))

        self.corroborator.cluster_event_claims(event_id, all_event_claims, source_ids)

        # Generate updated brief
        new_brief = self.brief_generator.generate_brief(
            event_id=event_id,
            event_title=event.label,
            event_category=event_category,
        )

        version_count = len(new_brief.version_history) + (1 if prev_brief else 0)
        curr_version = f"v1.{version_count}.0"
        prev_version = f"v1.{max(0, version_count - 1)}.0"

        # Compute diff
        diff = self.compute_brief_diff(prev_brief, new_brief, prev_version, curr_version)
        new_brief.version_history.append(f"{curr_version} ({diff.summary_of_changes})")

        # Cache new brief
        self._brief_cache[event_id] = new_brief

        # Export updated markdown & HTML
        out_dir = output_dir or Path("data/briefs")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{event_id}.md").write_text(MarkdownBriefRenderer().render(new_brief), encoding="utf-8")
        (out_dir / f"{event_id}.html").write_text(HtmlBriefRenderer().render(new_brief), encoding="utf-8")

        # Audit entry
        self.storage.write_audit_entry(
            AuditEntry(
                stage="continuous_update",
                stage_version=STAGE_VERSION,
                input_id=item.id,
                output_id=event_id,
                what_changed=f"Updated event {event_id} with item {item.id}: {diff.summary_of_changes}",
                when=datetime.now(timezone.utc),
            )
        )

        return event, new_brief, diff

    def handle_retraction(
        self,
        item_id: str,
        reason: str = "Publisher Retraction Notice",
        output_dir: Optional[Path] = None,
    ) -> list[tuple[Event, Brief, BriefDiff]]:
        """Applies a retraction to an article and all its extracted claims, updating affected event briefs."""
        item = self.storage.get_item(item_id)
        if not item:
            return []

        # Find all passages and claims
        passages = self.storage.get_passages_by_item(item_id)
        retracted_claim_texts: list[str] = []
        for p in passages:
            claims = self.storage.get_claims_by_passage(p.id)
            for c in claims:
                c.status = ClaimStatus.REJECTED
                self.storage.save_claim(c)
                retracted_claim_texts.append(c.neutralized_wording or c.original_wording)

        # Audit retraction
        self.storage.write_audit_entry(
            AuditEntry(
                stage="retraction_handling",
                stage_version=STAGE_VERSION,
                input_id=item_id,
                output_id=None,
                what_changed=f"Retracted item '{item.title}' ({len(retracted_claim_texts)} claims rejected). Reason: {reason}",
                when=datetime.now(timezone.utc),
            )
        )

        results: list[tuple[Event, Brief, BriefDiff]] = []

        # Find all events containing this item
        with self.storage._get_connection() as conn:
            rows = conn.execute("SELECT id FROM events").fetchall()
            all_event_ids = [r["id"] for r in rows]

        for ev_id in all_event_ids:
            event = self.storage.get_event(ev_id)
            if event and item_id in event.member_item_ids:
                prev_brief = self._brief_cache.get(ev_id)

                # Re-corroborate without retracted claims
                all_claims = [self.storage.get_claim(cid) for cid in event.claim_ids]
                active_claims = [c for c in all_claims if c and c.status != ClaimStatus.REJECTED]

                active_items = [self.storage.get_item(iid) for iid in event.member_item_ids if iid != item_id]
                source_ids = sorted(list(set(it.source_id for it in active_items if it)))

                self.corroborator.cluster_event_claims(ev_id, active_claims, source_ids)

                new_brief = self.brief_generator.generate_brief(ev_id, event.label)
                diff = self.compute_brief_diff(prev_brief, new_brief, "v1.0.0", "v1.1.0-retracted")
                diff.retracted_claims = retracted_claim_texts
                diff.summary_of_changes = f"Retracted item {item_id}: {len(retracted_claim_texts)} claim(s) removed"
                new_brief.version_history.append(f"Retraction applied: {diff.summary_of_changes}")

                self._brief_cache[ev_id] = new_brief

                out_dir = output_dir or Path("data/briefs")
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / f"{ev_id}.md").write_text(MarkdownBriefRenderer().render(new_brief), encoding="utf-8")
                (out_dir / f"{ev_id}.html").write_text(HtmlBriefRenderer().render(new_brief), encoding="utf-8")

                results.append((event, new_brief, diff))

        return results
