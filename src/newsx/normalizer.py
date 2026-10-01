"""Normalizer and Passage Segmentation Component (M2).

Strips HTML boilerplate, preserves quote and honorific boundaries,
segments text into sentence-level Passage records, and resolves relative dates (spec §6).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from bs4 import BeautifulSoup

from .schemas import AuditEntry, Item, Passage, PassageType
from .storage import Storage

STAGE_VERSION = "1.0.0"

# Common abbreviations and honorifics that should not cause sentence splits
PROTECTED_PREFIXES = {
    "mr", "mrs", "ms", "dr", "prof", "gov", "sen", "rep", "gen", "col", "capt",
    "u.s", "u.k", "e.u", "u.n", "e.g", "i.e", "vs", "corp", "inc", "ltd",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
}

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def clean_html_boilerplate(html_content: str) -> str:
    """Strips navigation, ad elements, and boilerplate from HTML."""
    if not html_content or "<" not in html_content:
        return html_content.strip()

    soup = BeautifulSoup(html_content, "html.parser")
    for bad_tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "svg", "noscript"]):
        bad_tag.decompose()

    # Remove elements by common ad/share classes
    for ad_elem in soup.find_all(class_=re.compile(r"(ad|advertisement|share|social|newsletter|cookie)", re.I)):
        ad_elem.decompose()

    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all(["p", "h1", "h2", "h3", "li"])]
    paragraphs = [p for p in paragraphs if len(p.split()) >= 4]
    return "\n".join(paragraphs)


def split_sentences_preserving_quotes(text: str) -> list[str]:
    """Splits a body of text into sentence passages while keeping quotes and abbreviations intact."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    all_sentences: list[str] = []

    for line in lines:
        # Regex to split on sentence ends (. ! ?) while ignoring abbreviations and quotes
        # Walk through characters with quote state tracking
        sentences = []
        current: list[str] = []
        in_double_quote = False
        in_single_quote = False

        chars = list(line)
        i = 0
        n = len(chars)

        while i < n:
            c = chars[i]
            if c == '"' or c == '“' or c == '”':
                in_double_quote = not in_double_quote
            elif c == "'" or c == '‘' or c == '’':
                # Check if it's an apostrophe (surrounded by letters) or quote
                is_apostrophe = (i > 0 and i < n - 1 and chars[i - 1].isalnum() and chars[i + 1].isalnum())
                if not is_apostrophe:
                    in_single_quote = not in_single_quote

            current.append(c)

            # Check for sentence boundary: . ! ? followed by space or end of line, outside quotes
            if not in_double_quote and not in_single_quote and c in {".", "!", "?"}:
                # Check if this period is part of a protected abbreviation
                word_before = "".join(current).strip().rstrip(".!?").split()
                last_word = word_before[-1].lower() if word_before else ""
                
                # Check if next char is space or end of string
                next_is_space = (i + 1 == n) or (i + 1 < n and chars[i + 1] in {" ", "\t"})
                
                if next_is_space and last_word not in PROTECTED_PREFIXES:
                    # Look ahead to see if next character after whitespace is uppercase
                    rest = "".join(chars[i + 1:]).strip()
                    if not rest or rest[0].isupper() or rest[0] in {'"', "“", "'"}:
                        sentence_str = "".join(current).strip()
                        if sentence_str:
                            sentences.append(sentence_str)
                        current = []
            i += 1

        remainder = "".join(current).strip()
        if remainder:
            sentences.append(remainder)

        all_sentences.extend(sentences)

    return all_sentences


def resolve_relative_dates(text: str, anchor_dt: Optional[datetime]) -> str:
    """Resolves relative date words like 'Tuesday' or 'yesterday' relative to anchor publication date."""
    if not anchor_dt:
        return text

    resolved = text
    # Match standalone relative words
    # E.g., 'on Tuesday', 'reported today', 'yesterday'
    if "yesterday" in text.lower():
        y_date = (anchor_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        resolved = re.sub(r"\byesterday\b", f"yesterday ({y_date})", resolved, flags=re.I)

    if "today" in text.lower():
        t_date = anchor_dt.strftime("%Y-%m-%d")
        resolved = re.sub(r"\btoday\b", f"today ({t_date})", resolved, flags=re.I)

    return resolved


class Normalizer:
    """Normalizes raw articles and segments them into atomic passages."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def normalize_item(self, item: Item) -> list[Passage]:
        # 1. Clean boilerplate
        cleaned = clean_html_boilerplate(item.cleaned_text)
        item.cleaned_text = cleaned

        # 2. Segment sentences
        sentences = split_sentences_preserving_quotes(cleaned)
        if not sentences and cleaned.strip():
            sentences = [cleaned.strip()]

        # 3. Create Passage records
        passages: list[Passage] = []
        for idx, s_text in enumerate(sentences):
            # Resolve relative dates
            resolved_text = resolve_relative_dates(s_text, item.published_time)

            # Assign basic heuristic passage type for M2 (refined by triage in M3)
            p_type = PassageType.OBSERVED_EVENT
            if any(char.isdigit() for char in resolved_text) and any(
                w in resolved_text.lower() for w in ["percent", "%", "$", "€", "billion", "million", "votes", "rate"]
            ):
                p_type = PassageType.QUANTITATIVE
            elif any(
                verb in resolved_text.lower()
                for verb in ["said", "stated", "announced", "reported", "warned", "argued", "claimed", "told"]
            ) or '"' in resolved_text or '“' in resolved_text:
                p_type = PassageType.ATTRIBUTED_STATEMENT

            passage_id = f"psg-{item.id}-{idx:03d}"
            passages.append(
                Passage(
                    id=passage_id,
                    item_id=item.id,
                    position=idx,
                    text=resolved_text,
                    passage_type=p_type,
                )
            )

        # Save to storage
        self.storage.save_item(item)
        self.storage.save_passages(passages)

        # Audit trail
        now = datetime.now(timezone.utc)
        self.storage.write_audit_entry(
            AuditEntry(
                stage="normalization",
                stage_version=STAGE_VERSION,
                input_id=item.id,
                output_id=None,
                what_changed=f"Normalized article and generated {len(passages)} passages",
                when=now,
            )
        )

        return passages
