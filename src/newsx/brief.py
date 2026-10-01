"""Event Brief Generator (Milestone 7).

Synthesizes structured, transparent event briefs from corroboration ledger entries,
claim provenance chains, source diversity audits, and timeline ordering.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from newsx.corroboration import Corroborator
from newsx.registry import DiversityChecker, SourceRegistry
from newsx.schemas import (
    ArticleType,
    AuditEntry,
    Brief,
    BriefFact,
    ChangeRecord,
    Claim,
    ConfidenceTier,
    DisputedPoint,
    Item,
    LedgerEntry,
    Passage,
    Source,
    SourceLedgerItem,
    SourceTier,
    TimelineEntry,
)
from newsx.storage import Storage

STAGE_VERSION = "1.0.0"


class BriefGenerator:
    """Generates structured, multi-section neutral event briefs with complete source drill-down."""

    def __init__(self, storage: Storage, registry: SourceRegistry, diversity_checker: Optional[DiversityChecker] = None) -> None:
        self.storage = storage
        self.registry = registry
        self.diversity_checker = diversity_checker or DiversityChecker(registry)

    def generate_brief(self, event_id: str, event_title: Optional[str] = None, event_category: str = "hard_fact") -> Brief:
        """Constructs a complete Brief for the specified event."""
        # 1. Fetch all items, passages, claims, and ledger entries for this event
        items = self.storage.get_items_by_event(event_id)
        if not items:
            # Fallback: get all items if no event-specific tag
            items = self.storage.all_items()

        # Build lookup maps
        item_map: dict[str, Item] = {it.id: it for it in items}
        passage_map: dict[str, Passage] = {}
        all_claims: list[Claim] = []

        for item in items:
            passages = self.storage.get_passages_by_item(item.id)
            for p in passages:
                passage_map[p.id] = p
                claims = self.storage.get_claims_by_passage(p.id)
                all_claims.extend(claims)

        claim_map: dict[str, Claim] = {c.id: c for c in all_claims}

        # 2. Corroborate and get ledger entries
        all_source_ids = sorted(list({it.source_id for it in items}))
        corroborator = Corroborator(self.storage, self.registry)
        ledger_entries = self.storage.get_ledger_entries(event_id)
        if not ledger_entries:
            ledger_entries = corroborator.cluster_event_claims(event_id, all_claims, all_source_ids)

        # 3. Source Ledger & Diversity Evaluation
        event_sources: list[Source] = []
        source_ledger_items: list[SourceLedgerItem] = []
        source_links: list[str] = []

        for it in items:
            src = self.registry.get(it.source_id)
            if src and src not in event_sources:
                event_sources.append(src)
            if it.url:
                source_links.append(str(it.url))

        # Sort sources by tier
        tier_order = {SourceTier.PRIMARY: 0, SourceTier.SECONDARY: 1, SourceTier.TERTIARY: 2}
        event_sources.sort(key=lambda s: (tier_order.get(s.tier, 9), s.name))

        for src in event_sources:
            src_items = [it for it in items if it.source_id == src.id]
            is_independent = any(not it.republished_from and not it.duplicate_of for it in src_items)
            repub_from = next((it.republished_from for it in src_items if it.republished_from), None)
            source_ledger_items.append(
                SourceLedgerItem(
                    source_id=src.id,
                    name=src.name,
                    tier=src.tier,
                    independent_origin=is_independent,
                    republished_from=repub_from,
                )
            )

        norm_category = event_category.replace("_", "-")
        div_result = self.diversity_checker.evaluate(norm_category, [s.id for s in event_sources])

        # 4. Synthesize Neutral Headline
        neutral_headline = self._synthesize_headline(event_id, event_title, items, ledger_entries)

        # 5. Partition Facts into Core, Single-Source, Disputed, and Unknowns
        core_facts: list[BriefFact] = []
        single_source_facts: list[BriefFact] = []
        disputed_points: list[DisputedPoint] = []
        unknowns: list[str] = []
        processed_dispute_ids: set[str] = set()

        for entry in ledger_entries:
            # Reconstruct BriefFact from ledger entry and underlying claims
            fact = self._build_brief_fact(entry, claim_map, item_map, passage_map)

            if entry.confidence_tier in (ConfidenceTier.PRIMARY_CONFIRMED, ConfidenceTier.INDEPENDENTLY_CORROBORATED):
                core_facts.append(fact)
            elif entry.confidence_tier == ConfidenceTier.SINGLE_SOURCE:
                single_source_facts.append(fact)
            elif entry.confidence_tier == ConfidenceTier.DISPUTED:
                if entry.id not in processed_dispute_ids:
                    # Gather all paired contradictions
                    conflicting_entries = [entry]
                    for contra_id in entry.contradictions:
                        contra_entry = next((e for e in ledger_entries if e.id == contra_id), None)
                        if contra_entry and contra_entry not in conflicting_entries:
                            conflicting_entries.append(contra_entry)
                            processed_dispute_ids.add(contra_entry.id)
                    processed_dispute_ids.add(entry.id)

                    dispute_facts = [
                        self._build_brief_fact(ce, claim_map, item_map, passage_map)
                        for ce in conflicting_entries
                    ]
                    topic = self._summarize_dispute_topic(dispute_facts)
                    explanation = self._generate_dispute_explanation(dispute_facts)
                    disputed_points.append(
                        DisputedPoint(
                            topic=topic,
                            claims=dispute_facts,
                            explanation=explanation,
                        )
                    )
            elif entry.confidence_tier == ConfidenceTier.UNVERIFIED_OR_RETRACTED:
                unknowns.append(f"Unverified or retracted claim: {fact.text}")

        # Rank Core Facts: Tier 1 (PRIMARY_CONFIRMED) first, then by independent origin count descending
        tier_weight = {ConfidenceTier.PRIMARY_CONFIRMED: 0, ConfidenceTier.INDEPENDENTLY_CORROBORATED: 1}
        core_facts.sort(key=lambda f: (tier_weight.get(f.tier, 9), -f.independent_source_count))

        # 6. Extract Chronological Timeline
        timeline = self._extract_timeline(all_claims, claim_map, item_map, passage_map, ledger_entries)

        # 7. Identify Unknowns / Missing reporting gaps
        if not any(f.tier == ConfidenceTier.PRIMARY_CONFIRMED for f in core_facts):
            unknowns.append("No primary official records or government filings have been captured yet.")
        if div_result.deficiencies:
            for defic in div_result.deficiencies:
                unknowns.append(f"Coverage Notice: {defic}")

        # 8. Build Brief Model
        brief = Brief(
            event_id=event_id,
            neutral_headline=neutral_headline,
            core_facts=core_facts,
            single_source_facts=single_source_facts,
            disputed_points=disputed_points,
            unknowns=unknowns,
            timeline=timeline,
            source_links=source_links,
            source_ledger=source_ledger_items,
            diversity_compliant=div_result.is_compliant,
            diversity_deficiencies=div_result.deficiencies,
            version_history=[f"v1.0.0 generated on {datetime.now(timezone.utc).isoformat()}"],
        )

        # 9. Audit Logging
        self.storage.write_audit_entry(
            AuditEntry(
                stage="brief_generation",
                stage_version=STAGE_VERSION,
                input_id=event_id,
                output_id=f"brief-{event_id}",
                what_changed=(
                    f"Generated brief '{neutral_headline}': "
                    f"{len(core_facts)} core facts, {len(disputed_points)} disputed points, "
                    f"{len(timeline)} timeline events."
                ),
                when=datetime.now(timezone.utc),
            )
        )

        return brief

    def _build_brief_fact(
        self,
        entry: LedgerEntry,
        claim_map: dict[str, Claim],
        item_map: dict[str, Item],
        passage_map: dict[str, Passage],
    ) -> BriefFact:
        """Constructs an enriched BriefFact containing text, attribution, URLs, and change records."""
        member_claims = [claim_map[cid] for cid in entry.equivalent_claim_ids if cid in claim_map]
        primary_claim = member_claims[0] if member_claims else None

        neutral_text = entry.canonical_claim
        orig_text = primary_claim.original_wording if primary_claim else neutral_text
        speaker = primary_claim.attribution_speaker if primary_claim else None
        is_anon = primary_claim.attribution_anonymous if primary_claim else False

        item_urls: list[str] = []
        passage_ids: list[str] = []
        all_changes: list[ChangeRecord] = []

        for c in member_claims:
            passage_ids.append(c.passage_id)
            all_changes.extend(c.changes)
            if len(c.provenance_chain) >= 2:
                item_id = c.provenance_chain[1]
                it = item_map.get(item_id)
                if it and it.url and str(it.url) not in item_urls:
                    item_urls.append(str(it.url))

        return BriefFact(
            claim_id=entry.id,
            tier=entry.confidence_tier,
            independent_source_count=entry.independent_origin_count,
            text=neutral_text,
            original_text=orig_text,
            attribution_speaker=speaker,
            attribution_anonymous=is_anon,
            supporting_source_ids=entry.supporting_source_ids,
            item_urls=item_urls,
            passage_ids=list(set(passage_ids)),
            changes=all_changes,
        )

    def _synthesize_headline(
        self,
        event_id: str,
        event_title: Optional[str],
        items: list[Item],
        ledger_entries: list[LedgerEntry],
    ) -> str:
        """Synthesizes a neutral, factual headline without sensationalism or editorializing."""
        if event_title and not any(w in event_title.lower() for w in ["shocking", "bombshell", "outrage", "slams"]):
            return event_title.strip()

        # Find reporting articles
        reporting_items = [it for it in items if it.article_type == ArticleType.REPORTING and it.title]
        if reporting_items:
            # Pick the cleanest title without clickbait punctuation
            cleanest = min(reporting_items, key=lambda it: len(re.findall(r"[\?!]", it.title)))
            # Strip editorial labels
            clean_title = re.sub(r"^(REPORT|BREAKING|EXCLUSIVE|WATCH):\s*", "", cleanest.title, flags=re.IGNORECASE)
            return clean_title.strip()

        if ledger_entries:
            # Use top canonical claim
            top = ledger_entries[0].canonical_claim
            return top.rstrip(".")

        return f"Event Brief: {event_id}"

    def _summarize_dispute_topic(self, facts: list[BriefFact]) -> str:
        """Determines the topic of a dispute."""
        combined = " ".join((f.text or "") for f in facts).lower()
        if "collision" in combined or "rammed" in combined or "shoal" in combined:
            return "Maritime Vessel Collision & Shoal Encounter"
        if "protest" in combined or "charges" in combined or "demonstrators" in combined:
            return "Protest Conduct & Police Enforcement Actions"
        if "fine" in combined or "wage" in combined or "percent" in combined or "%" in combined:
            return "Conflicting Quantitative Metric Assessments"
        return "Disputed Factual Assertions Across Outlets"

    def _generate_dispute_explanation(self, facts: list[BriefFact]) -> str:
        """Explains why the claims are in dispute."""
        sources = []
        for f in facts:
            sources.extend(f.supporting_source_ids)
        unique_srcs = ", ".join(sorted(set(sources)))
        return (
            f"Reporting outlets ({unique_srcs}) present mutually conflicting accounts or numeric figures. "
            "Both positions are presented side-by-side with original attributions pending primary verification."
        )

    def _extract_timeline(
        self,
        all_claims: list[Claim],
        claim_map: dict[str, Claim],
        item_map: dict[str, Item],
        passage_map: dict[str, Passage],
        ledger_entries: list[LedgerEntry],
    ) -> list[TimelineEntry]:
        """Extracts and chronologically orders temporal event milestones."""
        timeline_entries: list[TimelineEntry] = []
        seen_events: set[str] = set()

        for entry in ledger_entries:
            for cid in entry.equivalent_claim_ids:
                claim = claim_map.get(cid)
                if not claim:
                    continue

                time_str = claim.when
                if not time_str:
                    # Check if passage contains temporal expressions (e.g. Tuesday, 1:28 a.m., March 26)
                    psg = passage_map.get(claim.passage_id)
                    if psg:
                        m = re.search(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.|AM|PM)|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?)\b", psg.text)
                        if m:
                            time_str = m.group(1)

                if time_str:
                    clean_desc = claim.neutralized_wording or claim.original_wording
                    key = f"{time_str}:{clean_desc[:30]}"
                    if key not in seen_events:
                        seen_events.add(key)
                        timeline_entries.append(
                            TimelineEntry(
                                timestamp_str=time_str,
                                claim_id=claim.id,
                                description=clean_desc,
                                source_ids=claim.provenance_chain[:1] if claim.provenance_chain else [],
                                tier=entry.confidence_tier,
                            )
                        )

        # Sort timeline
        def _sort_key(entry: TimelineEntry) -> int:
            t = entry.timestamp_str.lower()
            # Order by time of day or day of week if possible
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for idx, d in enumerate(days):
                if d in t:
                    return idx * 1000
            if "a.m." in t or "am" in t:
                return 100
            if "p.m." in t or "pm" in t:
                return 200
            return 500

        timeline_entries.sort(key=_sort_key)
        return timeline_entries
