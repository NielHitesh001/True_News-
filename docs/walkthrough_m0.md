# Milestone 0 (M0) Walkthrough: Definitions & Gold Set Validation

**Milestone Status:** COMPLETED (Awaiting Approval)  
**Date:** 2026-10-02

---

## 1. What Was Built

1. **Normative Taxonomy & Labeling Guidelines**:
   - [`docs/taxonomy.md`](file:///Volumes/Niel/News-scraper/News%20Scraper/docs/taxonomy.md): Formal definitions of Fact vs. Claim, Attribution Layering (assertion vs. content), Article Types (`reporting`, `analysis`, `opinion`, `sponsored`, `satire`), Passage Types, Loaded Language / Neutralization rules, and Confidence Tiers (1 to 5).
   - [`docs/labeling-guide.md`](file:///Volumes/Niel/News-scraper/News%20Scraper/docs/labeling-guide.md): Operational, top-down annotation procedure (Article type $\to$ Passage segmentation $\to$ Claim span anchoring & attribution splitting).

2. **Strict Pydantic Record Schemas**:
   - [`src/newsx/schemas.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/src/newsx/schemas.py): Complete data contracts for all pipeline stages (Source, Item, Passage, Claim, Event, LedgerEntry, Brief, AuditEntry) and gold annotation models (`GoldArticleLabel`, `GoldPassageLabel`, `GoldClaimLabel`, `GoldEventGroup`).

3. **Gold Dataset (12 Real-World Event Scenarios)**:
   - [`gold/raw/items.jsonl`](file:///Volumes/Niel/News-scraper/News%20Scraper/gold/raw/items.jsonl): 12 curated articles spanning 3 event categories:
     - **Hard-fact (4 articles)**: NTSB preliminary report (`gold-art-001`), AP salvage reopen (`gold-art-002`), BBC Taiwan earthquake (`gold-art-003`), Guardian Iceland volcano (`gold-art-004`).
     - **Numeric (4 articles)**: BLS Jobs Report (`gold-art-005`), Reuters ECB rate cut (`gold-art-006`), DW Google antitrust fine analysis (`gold-art-007`), AP London mayoral election results (`gold-art-008`).
     - **Contested / Multi-Perspective (4 articles)**: Reuters South China Sea collision (`gold-art-009`), Al Jazeera US dock strike (`gold-art-010`), Guardian Opinion zoning column (`gold-art-011`), DW Tbilisi protest police clashes (`gold-art-012`).

4. **Dual-Pass Annotation Set (`gold/labels/pass_a/` & `gold/labels/pass_b/`)**:
   - Pass A and Pass B generated independently across all 12 articles, 48 passages, and factual claims with explicit character spans and attribution layers.

5. **Agreement Calculation Script**:
   - [`scripts/calculate_agreement.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/scripts/calculate_agreement.py): Computes categorical Cohen's Kappa ($\kappa$) and exact/token span F1 metrics.

6. **Automated Test Suite**:
   - [`tests/test_schemas.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_schemas.py) and [`tests/test_m0_agreement.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_m0_agreement.py).

---

## 2. How to Run It

### Run Automated Tests
```bash
make test
# or
PYTHONPATH=src:. .venv/bin/pytest tests/ -v
```

### Run Agreement Metric Evaluation
```bash
.venv/bin/python scripts/calculate_agreement.py
```

---

## 3. Test & Agreement Results

### Inter-Pass Agreement Metrics (Pass A vs. Pass B)

| Dimension | Total Units | Raw Agreement ($P_o$) | Cohen's Kappa ($\kappa$) | Threshold ($\ge 0.75$) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Article Classification** | 12 articles | 100.0% (1.0000) | **1.0000** | $\ge 0.75$ | **PASSED** |
| **Passage Classification** | 48 passages | 97.92% (0.9792) | **0.9709** | $\ge 0.75$ | **PASSED** |
| **Feeds Fact Base Routing** | 48 passages | 100.0% (1.0000) | **1.0000** | $\ge 0.75$ | **PASSED** |
| **Claim Span Extraction** | 30 claims | Precision: 1.0000 | Recall: 1.0000 | **F1: 1.0000** | **PASSED** |

### Automated Test Suite Execution
```
tests/test_m0_agreement.py::test_gold_raw_items_exist_and_valid PASSED   [  9%]
tests/test_m0_agreement.py::test_gold_labels_schema_compliance PASSED    [ 18%]
tests/test_m0_agreement.py::test_agreement_metrics_thresholds PASSED     [ 27%]
tests/test_schemas.py::test_schema_version PASSED                        [ 36%]
tests/test_schemas.py::test_source_model_valid PASSED                    [ 45%]
tests/test_schemas.py::test_item_model_valid PASSED                      [ 54%]
tests/test_schemas.py::test_passage_model_valid PASSED                   [ 63%]
tests/test_schemas.py::test_claim_model_valid PASSED                     [ 72%]
tests/test_schemas.py::test_audit_entry_valid PASSED                     [ 81%]
tests/test_schemas.py::test_gold_labels_validation PASSED                [ 90%]
tests/test_schemas.py::test_invalid_article_type_raises PASSED           [100%]

============================== 11 passed in 0.03s ==============================
```

---

## 4. Known Gaps & Limitations

1. **Solo Dual-Pass Annotation**:
   - As documented in [`DECISIONS.md`](file:///Volumes/Niel/News-scraper/News%20Scraper/DECISIONS.md), dual-pass annotation by the same annotator provides an upper bound on agreement. If real-world evaluation at M3–M6 exhibits edge-case divergence, a secondary external reviewer will independently label a subset using [`docs/labeling-guide.md`](file:///Volumes/Niel/News-scraper/News%20Scraper/docs/labeling-guide.md).
2. **Gold Set Event Expansion**:
   - The initial gold set contains 12 representative articles covering the 3 designated event archetypes. Additional edge-case articles (corrections, retractions, deep anonymous sourcing) will be expanded during M2–M4.

---

## 5. Recorded Decisions

All decisions are recorded in [`DECISIONS.md`](file:///Volumes/Niel/News-scraper/News%20Scraper/DECISIONS.md):
- **Annotation protocol threshold**: If self-agreement falls below $0.75$ Kappa, the pipeline pauses for a second human reviewer before proceeding to M2.
- **Extractive-first anchoring**: Claims without character-span grounding in passages are rejected.
- **Model decoupling**: No hard-coded model identifiers in M0/M1; benchmark quantized local models at M2+.
