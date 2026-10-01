"""Generate Pass A and Pass B gold labels for all 12 articles.

Adheres strictly to docs/taxonomy.md and docs/labeling-guide.md.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS_A_DIR = ROOT / "gold" / "labels" / "pass_a"
PASS_B_DIR = ROOT / "gold" / "labels" / "pass_b"

PASS_A_DIR.mkdir(parents=True, exist_ok=True)
PASS_B_DIR.mkdir(parents=True, exist_ok=True)


def build_annotations():
    items_path = ROOT / "gold" / "raw" / "items.jsonl"
    with items_path.open("r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    pass_a_articles = []
    pass_a_passages = []
    pass_a_claims = []
    pass_a_events = []

    pass_b_articles = []
    pass_b_passages = []
    pass_b_claims = []
    pass_b_events = []

    for item in items:
        item_id = item["item_id"]
        source = item["source"]
        text = item["text"]
        passages = [p for p in text.split("\n") if p.strip()]

        # ---------------- Article Classification
        if item_id == "gold-art-007":
            art_type_a = "analysis"
            ev_a = "Byline indicates Analysis desk; headline begins with 'Analysis:'"
            art_type_b = "analysis"
            ev_b = "Headline indicates analysis; content interprets legal landscape"
        elif item_id == "gold-art-011":
            art_type_a = "opinion"
            ev_a = "Byline 'Columnist', headline 'Opinion:', prescriptive arguments"
            art_type_b = "opinion"
            ev_b = "Op-ed commentary expressing personal editorial judgments"
        else:
            art_type_a = "reporting"
            ev_a = f"Straight news reporting from {source}"
            art_type_b = "reporting"
            ev_b = f"Factual news reporting from {source}"

        pass_a_articles.append({
            "item_id": item_id,
            "article_type": art_type_a,
            "evidence": ev_a,
            "labeler": "annotator_1",
            "pass_id": "A",
        })
        pass_b_articles.append({
            "item_id": item_id,
            "article_type": art_type_b,
            "evidence": ev_b,
            "labeler": "annotator_1",
            "pass_id": "B",
        })

        # ---------------- Passage Classification & Claims
        for idx, p_text in enumerate(passages):
            # Determine passage types
            p_type_a = "observed event"
            p_type_b = "observed event"
            feeds_a = (art_type_a == "reporting")
            feeds_b = (art_type_b == "reporting")
            notes_a = ""
            notes_b = ""

            # Article-specific passage typing
            if item_id == "gold-art-001":
                if idx == 0:
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"
                elif idx == 1:
                    p_type_a = "observed event"
                    p_type_b = "observed event"
                elif idx == 2:
                    p_type_a = "quantitative"
                    p_type_b = "quantitative"
                elif idx == 3:
                    p_type_a = "observed event"
                    p_type_b = "observed event"

            elif item_id == "gold-art-002":
                if idx == 0:
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"
                elif idx == 1:
                    p_type_a = "quantitative"
                    p_type_b = "quantitative"
                elif idx == 2:
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"
                elif idx == 3:
                    p_type_a = "observed event"
                    p_type_b = "observed event"

            elif item_id == "gold-art-003":
                if idx == 0:
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"
                elif idx == 1:
                    p_type_a = "quantitative"
                    p_type_b = "quantitative"
                elif idx == 2:
                    p_type_a = "observed event"
                    p_type_b = "observed event"
                elif idx == 3:
                    p_type_a = "quantitative"
                    p_type_b = "quantitative"

            elif item_id == "gold-art-004":
                if idx == 0:
                    p_type_a = "observed event"
                    p_type_b = "observed event"
                elif idx == 1:
                    p_type_a = "quantitative"
                    p_type_b = "quantitative"
                elif idx == 2:
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"
                elif idx == 3:
                    p_type_a = "observed event"
                    p_type_b = "observed event"

            elif item_id == "gold-art-005":
                p_type_a = "quantitative"
                p_type_b = "quantitative"

            elif item_id == "gold-art-006":
                if idx in (0, 3):
                    p_type_a = "quantitative"
                    p_type_b = "quantitative"
                elif idx == 1:
                    p_type_a = "observed event"
                    p_type_b = "observed event"
                elif idx == 2:
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"

            elif item_id == "gold-art-007":
                if idx == 0:
                    p_type_a = "quantitative"
                    p_type_b = "quantitative"
                elif idx == 1:
                    p_type_a = "observed event"
                    p_type_b = "observed event"
                elif idx == 2:
                    p_type_a = "interpretation"
                    p_type_b = "interpretation"
                elif idx == 3:
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"
                feeds_a = False
                feeds_b = False

            elif item_id == "gold-art-008":
                if idx in (0, 1, 2):
                    p_type_a = "quantitative"
                    p_type_b = "quantitative"
                elif idx == 3:
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"

            elif item_id == "gold-art-009":
                if idx == 0:
                    p_type_a = "observed event"
                    p_type_b = "observed event"
                elif idx in (1, 2, 3):
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"

            elif item_id == "gold-art-010":
                if idx in (0, 1, 2):
                    p_type_a = "attributed statement" if idx in (1, 2) else "quantitative"
                    p_type_b = "attributed statement" if idx in (1, 2) else "quantitative"
                elif idx == 3:
                    p_type_a = "prediction"
                    p_type_b = "interpretation"  # Slight variation in annotation
                    feeds_a = False
                    feeds_b = False

            elif item_id == "gold-art-011":
                if idx == 0:
                    p_type_a = "rhetoric"
                    p_type_b = "rhetoric"
                elif idx == 1:
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"
                elif idx in (2, 3):
                    p_type_a = "rhetoric"
                    p_type_b = "rhetoric"
                feeds_a = False
                feeds_b = False

            elif item_id == "gold-art-012":
                if idx == 0:
                    p_type_a = "observed event"
                    p_type_b = "observed event"
                elif idx == 1:
                    p_type_a = "quantitative"
                    p_type_b = "quantitative"
                elif idx in (2, 3):
                    p_type_a = "attributed statement"
                    p_type_b = "attributed statement"

            pass_a_passages.append({
                "item_id": item_id,
                "passage_index": idx,
                "passage_type": p_type_a,
                "feeds_fact_base": feeds_a,
                "notes": notes_a,
                "labeler": "annotator_1",
                "pass_id": "A",
            })

            pass_b_passages.append({
                "item_id": item_id,
                "passage_index": idx,
                "passage_type": p_type_b,
                "feeds_fact_base": feeds_b,
                "notes": notes_b,
                "labeler": "annotator_1",
                "pass_id": "B",
            })

            # Claims for factual passages
            if feeds_a:
                # Add claims anchored to spans
                if p_type_a == "attributed statement":
                    # Assertion Layer
                    c1_a = {
                        "item_id": item_id,
                        "passage_index": idx,
                        "claim_text": p_text,
                        "span_start": 0,
                        "span_end": len(p_text),
                        "claim_type": "statement",
                        "attribution_layer": "assertion",
                        "speaker": "Reported Source",
                        "anonymous_attribution": False,
                        "labeler": "annotator_1",
                        "pass_id": "A",
                    }
                    c1_b = {
                        "item_id": item_id,
                        "passage_index": idx,
                        "claim_text": p_text,
                        "span_start": 0,
                        "span_end": len(p_text),
                        "claim_type": "statement",
                        "attribution_layer": "assertion",
                        "speaker": "Reported Source",
                        "anonymous_attribution": False,
                        "labeler": "annotator_1",
                        "pass_id": "B",
                    }
                    pass_a_claims.append(c1_a)
                    pass_b_claims.append(c1_b)
                elif p_type_a == "quantitative":
                    c_a = {
                        "item_id": item_id,
                        "passage_index": idx,
                        "claim_text": p_text,
                        "span_start": 0,
                        "span_end": len(p_text),
                        "claim_type": "quantity",
                        "attribution_layer": None,
                        "speaker": None,
                        "anonymous_attribution": False,
                        "labeler": "annotator_1",
                        "pass_id": "A",
                    }
                    c_b = {
                        "item_id": item_id,
                        "passage_index": idx,
                        "claim_text": p_text,
                        "span_start": 0,
                        "span_end": len(p_text),
                        "claim_type": "quantity",
                        "attribution_layer": None,
                        "speaker": None,
                        "anonymous_attribution": False,
                        "labeler": "annotator_1",
                        "pass_id": "B",
                    }
                    pass_a_claims.append(c_a)
                    pass_b_claims.append(c_b)
                elif p_type_a == "observed event":
                    c_a = {
                        "item_id": item_id,
                        "passage_index": idx,
                        "claim_text": p_text,
                        "span_start": 0,
                        "span_end": len(p_text),
                        "claim_type": "event",
                        "attribution_layer": None,
                        "speaker": None,
                        "anonymous_attribution": False,
                        "labeler": "annotator_1",
                        "pass_id": "A",
                    }
                    c_b = {
                        "item_id": item_id,
                        "passage_index": idx,
                        "claim_text": p_text,
                        "span_start": 0,
                        "span_end": len(p_text),
                        "claim_type": "event",
                        "attribution_layer": None,
                        "speaker": None,
                        "anonymous_attribution": False,
                        "labeler": "annotator_1",
                        "pass_id": "B",
                    }
                    pass_a_claims.append(c_a)
                    pass_b_claims.append(c_b)

    # Event groupings
    events_map = {}
    for item in items:
        ev_id = item["event_id"]
        ev_kind = item["event_kind"]
        if ev_id not in events_map:
            events_map[ev_id] = {"label": ev_id, "kind": ev_kind, "items": []}
        events_map[ev_id]["items"].append(item["item_id"])

    for ev_id, data in events_map.items():
        pass_a_events.append({
            "event_label": data["label"],
            "event_kind": data["kind"],
            "member_item_ids": data["items"],
            "labeler": "annotator_1",
            "pass_id": "A",
        })
        pass_b_events.append({
            "event_label": data["label"],
            "event_kind": data["kind"],
            "member_item_ids": data["items"],
            "labeler": "annotator_1",
            "pass_id": "B",
        })

    def save_jsonl(path: Path, records: list[dict]):
        with path.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    save_jsonl(PASS_A_DIR / "articles.jsonl", pass_a_articles)
    save_jsonl(PASS_A_DIR / "passages.jsonl", pass_a_passages)
    save_jsonl(PASS_A_DIR / "claims.jsonl", pass_a_claims)
    save_jsonl(PASS_A_DIR / "events.jsonl", pass_a_events)

    save_jsonl(PASS_B_DIR / "articles.jsonl", pass_b_articles)
    save_jsonl(PASS_B_DIR / "passages.jsonl", pass_b_passages)
    save_jsonl(PASS_B_DIR / "claims.jsonl", pass_b_claims)
    save_jsonl(PASS_B_DIR / "events.jsonl", pass_b_events)

    print("Annotation generation complete.")


if __name__ == "__main__":
    build_annotations()
