# Milestone 4 (M4) Walkthrough: Claim Extraction

**Milestone Status:** COMPLETED (Awaiting Approval)  
**Date:** 2026-10-02

---

## 1. What Was Built

1. **Swappable Model Interface & Disk Cache (`src/newsx/models.py`)**:
   - `BaseModelClient` interface with deterministic SHA-256 disk caching (`data/cache/`), fixed temperature=0.0, and seed=42.
   - `DeterministicExtractorClient` for reproducible, zero-dependency offline extraction.
   - `OllamaModelClient` for local open-weight model serving.

2. **Extractive Claim Extractor (`src/newsx/extractor.py`)**:
   - **Extractive-First Span Grounding**: Validates that every extracted claim is an exact character-span substring of the source passage. Unanchored candidate claims are assigned `status = ClaimStatus.REJECTED`.
   - **Attribution Layering**: Splits attributed statements into two distinct claims:
     1. **Assertion Layer**: The fact that the statement was publicly uttered (`claim_type = statement`, `attribution_speaker = ...`, `attribution_anonymous = bool`).
     2. **Content Layer**: The proposition stated, assigned its own claim type (`event`, `quantity`, `causal`).
   - **Semantic Slot Parsing**: Extracts `who`, `what`, `when`, `where`, and `how_much` without ungrounded filling-in.
   - **Provenance Chain**: Attaches a 3-tier immutable provenance array `[source_id, item_id, passage_id]` to every claim.

3. **Storage & Pipeline Integration (`src/newsx/storage.py` & `src/newsx/pipeline.py`)**:
   - Stores `Claim` records in SQLite `claims` table and associates `claim_ids` with parent `Event` records.
   - Writes `claim_extraction` audit entries recording the model ID and settings hash.

4. **Gold Set Evaluation Script & Automated Test Suite**:
   - [`scripts/evaluate_claims.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/scripts/evaluate_claims.py): Evaluates span grounding F1, claim type accuracy, and attribution layer accuracy against human-labeled gold claims (`gold/labels/pass_a/claims.jsonl`).
   - [`tests/test_models.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_models.py), [`tests/test_extractor.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_extractor.py), and [`tests/test_m4_gold_evaluation.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_m4_gold_evaluation.py).

---

## 2. How to Run It

### Run All Automated Tests
```bash
make test
```

### Run Gold Set Claim Extraction Benchmark
```bash
.venv/bin/python scripts/evaluate_claims.py
```

### Run Pipeline with Claim Extraction on an Event
```bash
make run EVENT=event-key-bridge-01
```

---

## 3. Benchmark & Test Results

### Gold Set Benchmark Performance (vs. Gold Set Pass A)

| Evaluation Metric | Measured Score | Target Threshold | Status |
| :--- | :--- | :--- | :--- |
| **Span Grounding F1 Score** | **1.0000** (Precision: 1.0000 \| Recall: 1.0000) | $\ge 0.85$ | **PASSED** |
| **Provenance Completeness** | **100.0%** (3-tier chain: Source $\to$ Item $\to$ Passage) | $100\%$ | **PASSED** |
| **Claim Type Accuracy** | **82.05%** | $\ge 80\%$ | **PASSED** |
| **Attribution Layer Accuracy** | **82.05%** | $\ge 80\%$ | **PASSED** |
| **Unanchored / Rejected Claims** | **0** (All extracted claims verified against raw text spans) | 0 ungrounded | **PASSED** |

### Automated Test Suite Execution (46 Tests Total)
```
============================= test session starts ==============================
collected 46 items                                                             

tests/test_collector.py::test_collector_ingest_raw_record PASSED         [  2%]
tests/test_collector.py::test_collector_rss_parser PASSED                [  4%]
tests/test_deduplication.py::test_jaccard_similarity_calculation PASSED  [  6%]
tests/test_deduplication.py::test_deduplicator_republish_detection PASSED [  8%]
tests/test_diversity.py::test_diversity_evaluator_hard_fact_compliant PASSED [ 10%]
tests/test_diversity.py::test_diversity_evaluator_missing_primary_deficiency PASSED [ 13%]
tests/test_diversity.py::test_diversity_evaluator_tertiary_ratio_violation PASSED [ 15%]
tests/test_diversity.py::test_diversity_evaluator_contested_rules PASSED [ 17%]
tests/test_diversity.py::test_transparency_page_generation PASSED        [ 19%]
tests/test_extractor.py::test_extractor_attributed_statement PASSED      [ 21%]
tests/test_extractor.py::test_extractor_quantitative_slots PASSED        [ 23%]
tests/test_extractor.py::test_extractor_opinion_article_produces_no_claims PASSED [ 26%]
tests/test_m0_agreement.py::test_gold_raw_items_exist_and_valid PASSED   [ 28%]
tests/test_m0_agreement.py::test_gold_labels_schema_compliance PASSED    [ 30%]
tests/test_m0_agreement.py::test_agreement_metrics_thresholds PASSED     [ 32%]
tests/test_m2_pipeline.py::test_pipeline_run_event PASSED                [ 34%]
tests/test_m2_pipeline.py::test_pipeline_run_all_gold_events PASSED      [ 36%]
tests/test_m3_gold_evaluation.py::test_triage_gold_benchmark_accuracy_thresholds PASSED [ 39%]
tests/test_m4_gold_evaluation.py::test_claim_extraction_gold_benchmark PASSED [ 41%]
tests/test_models.py::test_model_client_caching PASSED                   [ 43%]
tests/test_models.py::test_deterministic_extractor_client PASSED         [ 45%]
tests/test_normalizer.py::test_clean_html_boilerplate PASSED             [ 47%]
tests/test_normalizer.py::test_split_sentences_preserving_quotes PASSED  [ 50%]
tests/test_normalizer.py::test_split_sentences_with_abbreviations PASSED [ 52%]
tests/test_normalizer.py::test_resolve_relative_dates PASSED             [ 54%]
tests/test_normalizer.py::test_normalizer_pipeline PASSED                [ 56%]
tests/test_schemas.py::test_schema_version PASSED                        [ 58%]
tests/test_schemas.py::test_source_model_valid PASSED                    [ 60%]
tests/test_schemas.py::test_item_model_valid PASSED                      [ 63%]
tests/test_schemas.py::test_passage_model_valid PASSED                   [ 65%]
tests/test_schemas.py::test_claim_model_valid PASSED                     [ 67%]
tests/test_schemas.py::test_audit_entry_valid PASSED                     [ 69%]
tests/test_schemas.py::test_gold_labels_validation PASSED                [ 71%]
tests/test_schemas.py::test_invalid_article_type_raises PASSED           [ 73%]
tests/test_source_registry.py::test_source_registry_loads_default_config PASSED [ 76%]
tests/test_source_registry.py::test_source_registry_tiers_coverage PASSED [ 78%]
tests/test_source_registry.py::test_source_registry_lookup PASSED        [ 80%]
tests/test_storage.py::test_storage_source_crud PASSED                   [ 82%]
tests/test_storage.py::test_storage_item_and_passages PASSED             [ 84%]
tests/test_storage.py::test_storage_audit_log PASSED                     [ 86%]
tests/test_triage.py::test_article_triager_opinion_url PASSED            [ 89%]
tests/test_triage.py::test_article_triager_analysis_headline PASSED      [ 91%]
tests/test_triage.py::test_article_triager_sponsored_content PASSED      [ 93%]
tests/test_triage.py::test_passage_triager_rhetoric_routing PASSED       [ 95%]
tests/test_triage.py::test_passage_triager_quantitative_reporting PASSED [ 97%]
tests/test_triage.py::test_passage_triager_analysis_excluded_from_fact_base PASSED [100%]

============================== 46 passed in 0.43s ==============================
```

---

## 4. Decisions Recorded

Updated [`DECISIONS.md`](file:///Volumes/Niel/News-scraper/News%20Scraper/DECISIONS.md):
- **Extractive-First Anchoring**: Rejection of any candidate claim without an exact substring match in the passage.
- **Dual Attribution Layers**: Separation of public announcement utterance (Layer 1) from the propositional payload (Layer 2).
- **Anonymous Sourcing**: Flagging group/anonymous attributions (`officials`, `sources`, `critics`) as `attribution_anonymous = True`.
- **Model Caching**: Prompt SHA-256 caching for deterministic evaluation.
