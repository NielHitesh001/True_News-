"""Neutralization Engine and Meaning Preservation Checker (M5).

Neutralizes loaded, emotional, or charged language into plain measurable wording,
records reversible change traces (ChangeRecord), and enforces strict meaning preservation (spec §3/§4/§5/§6).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import yaml

from .schemas import AuditEntry, ChangeRecord, Claim, ClaimStatus
from .storage import Storage

DEFAULT_NEUTRALIZATION_RULES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "neutralization_rules.yaml"
)
STAGE_VERSION = "1.0.0"


class MeaningChecker:
    """Verifies that neutralized text preserves the full factual meaning of the original."""

    def __init__(self, whitelist: list[str]) -> None:
        self.whitelist = whitelist

    def verify(self, original: str, neutralized: str, claim: Optional[Claim] = None) -> tuple[bool, str]:
        if not neutralized.strip():
            return False, "Neutralized text is empty"

        orig_lower = original.lower()
        neut_lower = neutralized.lower()

        # 1. Number & Quantity Preservation
        orig_numbers = set(re.findall(r"\b\d+[\d,\.]*\b", original))
        neut_numbers = set(re.findall(r"\b\d+[\d,\.]*\b", neutralized))
        missing_numbers = orig_numbers - neut_numbers
        if missing_numbers:
            return False, f"Missing factual numbers: {missing_numbers}"

        # 2. Currency & Percentage Symbols Preservation
        for sym in ["$", "€", "£", "%"]:
            if sym in original and sym not in neutralized:
                return False, f"Missing factual unit/currency symbol '{sym}'"

        # 3. Factual Whitelist Preservation (e.g. hospitalized, killed, died, injured)
        for term in self.whitelist:
            if re.search(rf"\b{re.escape(term)}\b", orig_lower) and not re.search(
                rf"\b{re.escape(term)}\b", neut_lower
            ):
                return False, f"Factual consequence '{term}' was erroneously removed"

        # 4. Slot Entity & Date Preservation (if provided via Claim)
        if claim:
            if claim.where and claim.where.lower() not in neut_lower:
                return False, f"Missing location entity '{claim.where}'"
            if claim.when and claim.when.lower() not in neut_lower:
                return False, f"Missing temporal anchor '{claim.when}'"

        return True, "Meaning strictly preserved"


class Neutralizer:
    """Rewrites extracted claims into neutral, measurable propositions with change tracking."""

    def __init__(
        self,
        storage: Storage,
        rules_path: Optional[Path] = None,
    ) -> None:
        self.storage = storage
        self.rules_path = rules_path or DEFAULT_NEUTRALIZATION_RULES_PATH
        self._load_rules()

    def _load_rules(self) -> None:
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Neutralization rules not found at {self.rules_path}")

        with self.rules_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self.categories = data.get("categories", {})
        self.whitelist = data.get("factual_whitelist", [])
        self.meaning_checker = MeaningChecker(self.whitelist)

    def _clean_spaces(self, text: str) -> str:
        # Collapse multiple spaces and fix punctuation spacing
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = re.sub(r"\s+([,\.\?!])", r"\1", cleaned)
        return cleaned

    def neutralize_claim(self, claim: Claim) -> Claim:
        original = claim.original_wording
        text = original
        changes: list[ChangeRecord] = []

        # Iterate through loaded categories in order
        for cat_name, rules in self.categories.items():
            for rule in rules:
                pattern = rule["match"]
                replacement = rule["replacement"]
                rationale = rule["rationale"]

                # Find all matches
                for m in re.finditer(pattern, text, re.I):
                    span_text = m.group(0)
                    # Don't replace if span text is in factual whitelist
                    if span_text.lower() in self.whitelist:
                        continue

                    # Apply substitution
                    new_text = re.sub(pattern, replacement, text, count=1, flags=re.I)
                    if new_text != text:
                        changes.append(
                            ChangeRecord(
                                original_span=span_text,
                                replacement=replacement,
                                category=cat_name.rstrip("s"),  # intensifiers -> intensifier
                                rationale=rationale,
                            )
                        )
                        text = new_text

        neutralized = self._clean_spaces(text)

        # If no changes were needed, neutralized_wording equals original
        if not changes:
            claim.neutralized_wording = original
            claim.changes = []
            claim.status = ClaimStatus.NEUTRALIZED
            return claim

        # Run Meaning Preservation Check
        passed, reason = self.meaning_checker.verify(original, neutralized, claim)

        if passed:
            claim.neutralized_wording = neutralized
            claim.changes = changes
            claim.status = ClaimStatus.NEUTRALIZED
        else:
            # Fallback on doubt: keep original, flag claim
            claim.neutralized_wording = None
            claim.changes = changes
            claim.status = ClaimStatus.FLAGGED
            claim.changes.append(
                ChangeRecord(
                    original_span="[REVERTED]",
                    replacement=original,
                    category="other",
                    rationale=f"Meaning preservation check failed: {reason}. Preserved original wording.",
                )
            )

        return claim

    def process_claims(self, claims: list[Claim]) -> list[Claim]:
        now = datetime.now(timezone.utc)
        processed: list[Claim] = []

        for claim in claims:
            updated = self.neutralize_claim(claim)
            self.storage.save_claim(updated)
            processed.append(updated)

            # Audit trail
            changes_summary = (
                f"Applied {len(updated.changes)} edits: "
                + "; ".join(f"'{c.original_span}' -> '{c.replacement}'" for c in updated.changes)
                if updated.changes
                else "No loaded wording detected"
            )
            self.storage.write_audit_entry(
                AuditEntry(
                    stage="neutralization",
                    stage_version=STAGE_VERSION,
                    input_id=claim.id,
                    output_id=claim.id,
                    what_changed=f"Neutralization status '{updated.status.value}'. {changes_summary}",
                    when=now,
                )
            )

        return processed
