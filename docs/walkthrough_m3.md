# Milestone 3 (M3) Walkthrough: Triage (Article & Passage Labeling)

**Milestone Status:** COMPLETED (Awaiting Approval)  
**Date:** 2026-10-02

---

## 1. What Was Built

1. **Configurable Triage Rules (`config/triage_rules.yaml`)**:
   - URL placement patterns (`/opinion`, `/commentisfree`, `/analysis`, `/sponsored`, `/brand-studio`, `/satire`).
   - Byline roles (`Columnist`, `Analysis desk`, `Brand Studio`).
   - Headline prefixes (`Opinion:`, `Analysis:`, `Explainer:`).
   - Content indicators for opinions, analysis, predictions, rhetoric, and quantitative measurements.

2. **Hierarchical Article Triager (`ArticleTriager` in `src/newsx/triage.py`)**:
   - Classifies items into `reporting`, `analysis`, `opinion`, `sponsored`, or `satire`.
   - Records classification evidence in the audit log.

3. **Passage Triager & Fact-Base Routing (`PassageTriager` in `src/newsx/triage.py`)**:
   - Classifies segmented passages into the 6 taxonomy types: `observed event`, `quantitative`, `attributed statement`, `interpretation`, `prediction`, `rhetoric`.
   - Enforces strict fact-base routing: `feeds_fact_base = True` only for `observed event`, `quantitative`, and `attributed statement` passages from `reporting` articles.
   - All passages from `opinion`, `analysis`, `sponsored`, and `satire` articles have `feeds_fact_base = False` and are held in separate labeled sections.

4. **Pipeline Integration (`src/newsx/pipeline.py`)**:
   - Pipeline automatically triages articles and passages during ingestion and updates SQLite records.

5. **Gold Set Evaluation Script & Automated Test Suite**:
   - [`scripts/evaluate_triage.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/scripts/evaluate_triage.py): Evaluates precision, recall, and Macro-F1 across classes vs. Gold Set Pass A.
   - [`tests/test_triage.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_triage.py) and [`tests/test_m3_gold_evaluation.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_m3_gold_evaluation.py).

---

## 2. How to Run It

### Run All Automated Tests
```bash
make test
```

### Run Gold Set Triage Benchmark
```bash
.venv/bin/python scripts/evaluate_triage.py
```

### Run Pipeline with Triage on an Event
```bash
make run EVENT=event-key-bridge-01
```

---

## 3. Benchmark & Test Results

### Gold Set Benchmark Performance (vs. Gold Set Pass A)

| Evaluation Task | Total Samples | Accuracy | Macro-F1 | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Article Triage** | 12 articles | **100.0% (1.0000)** | **1.0000** | **PASSED** ($\ge 90\%$) |
| **Fact-Base Routing** | 48 passages | **100.0% (1.0000)** | **1.0000** | **PASSED** ($\ge 95\%$) |
| **Passage Classification** | 48 passages | **83.33% (0.8333)** | **0.9045** | **PASSED** ($\ge 80\%$) |

#### Per-Class Breakdown:
- **Article Level**:
  - `reporting`: Precision: 1.000, Recall: 1.000, F1: 1.000 (N=10)
  - `analysis`: Precision: 1.000, Recall: 1.000, F1: 1.000 (N=1)
  - `opinion`: Precision: 1.000, Recall: 1.000, F1: 1.000 (N=1)
- **Passage Level**:
  - `interpretation`: Precision: 1.000, Recall: 1.000, F1: 1.000 (N=1)
  - `prediction`: Precision: 1.000, Recall: 1.000, F1: 1.000 (N=1)
  - `rhetoric`: Precision: 1.000, Recall: 1.000, F1: 1.000 (N=3)
  - `quantitative`: Precision: 0.739, Recall: 1.000, F1: 0.850 (N=17)
  - `observed event`: Precision: 0.818, Recall: 0.900, F1: 0.857 (N=10)
  - `attributed statement`: Precision: 1.000, Recall: 0.562, F1: 0.720 (N=16)

### Automated Test Suite Execution (40 Tests Total)
```
============================= test session starts ==============================
collected 40 items                                                             

tests/test_collector.py::test_collector_ingest_raw_record PASSED         [  2%]
tests/test_collector.py::test_collector_rss_parser PASSED                [  5%]
tests/test_deduplication.py::test_jaccard_similarity_calculation PASSED  [  7%]
tests/test_deduplication.py::test_deduplicator_republish_detection PASSED [ 10%]
tests/test_diversity.py::test_diversity_evaluator_hard_fact_compliant PASSED [ 12%]
tests/test_diversity.py::test_diversity_evaluator_missing_primary_deficiency PASSED [ 15%]
tests/test_diversity.py::test_diversity_evaluator_tertiary_ratio_violation PASSED [ 17%]
tests/test_diversity.py::test_diversity_evaluator_contested_rules PASSED [ 20%]
tests/test_diversity.py::test_transparency_page_generation PASSED        [ 22%]
tests/test_m0_agreement.py::test_gold_raw_items_exist_and_valid PASSED   [ 25%]
tests/test_m0_agreement.py::test_gold_labels_schema_compliance PASSED    [ 27%]
tests/test_m0_agreement.py::test_agreement_metrics_thresholds PASSED     [ 30%]
tests/test_m2_pipeline.py::test_pipeline_run_event PASSED                [ 32%]
tests/test_m2_pipeline.py::test_pipeline_run_all_gold_events PASSED      [ 35%]
tests/test_m3_gold_evaluation.py::test_triage_gold_benchmark_accuracy_thresholds PASSED [ 37%]
tests/test_normalizer.py::test_clean_html_boilerplate PASSED             [ 40%]
tests/test_normalizer.py::test_split_sentences_preserving_quotes PASSED  [ 42%]
tests/test_normalizer.py::test_split_sentences_with_abbreviations PASSED [ 45%]
tests/test_normalizer.py::test_resolve_relative_dates PASSED             [ 47%]
tests/test_normalizer.py::test_normalizer_pipeline PASSED                [ 50%]
tests/test_schemas.py::test_schema_version PASSED                        [ 52%]
tests/test_schemas.py::test_source_model_valid PASSED                    [ 55%]
tests/test_schemas.py::test_item_model_valid PASSED                      [ 57%]
tests/test_schemas.py::test_passage_model_valid PASSED                   [ 60%]
tests/test_schemas.py::test_claim_model_valid PASSED                     [ 62%]
tests/test_schemas.py::test_audit_entry_valid PASSED                     [ 65%]
tests/test_schemas.py::test_gold_labels_validation PASSED                [ 67%]
tests/test_schemas.py::test_invalid_article_type_raises PASSED           [ 70%]
tests/test_source_registry.py::test_source_registry_loads_default_config PASSED [ 72%]
tests/test_source_registry.py::test_source_registry_tiers_coverage PASSED [ 75%]
tests/test_source_registry.py::test_source_registry_lookup PASSED        [ 77%]
tests/test_storage.py::test_storage_source_crud PASSED                   [ 80%]
tests/test_storage.py::test_storage_item_and_passages PASSED             [ 82%]
tests/test_storage.py::test_storage_audit_log PASSED                     [ 85%]
tests/test_triage.py::test_article_triager_opinion_url PASSED            [ 87%]
tests/test_triage.py::test_article_triager_analysis_headline PASSED      [ 90%]
tests/test_triage.py::test_article_triager_sponsored_content PASSED      [ 92%]
tests/test_triage.py::test_passage_triager_rhetoric_routing PASSED       [ 95%]
tests/test_triage.py::test_passage_triager_quantitative_reporting PASSED [ 97%]
tests/test_triage.py::test_passage_triager_analysis_excluded_from_fact_base PASSED [100%]

============================== 40 passed in 0.31s ==============================
```

---

## 4. Decisions Recorded

Updated [`DECISIONS.md`](file:///Volumes/Niel/News-scraper/News%20Scraper/DECISIONS.md):
- **Hierarchical Ladder**: URL placement $\to$ Headline prefix $\to$ Byline role $\to$ Content indicators $\to$ Default reporting.
- **Strict Fact-Base Exclusion**: Complete exclusion of passages from opinion, analysis, sponsored, and satire articles from entering the fact base.
- **Quantitative Precedence**: Standalone numerical/metric occurrences without direct quotes prioritize `quantitative` over generic attribution verbs to avoid metric misclassification.
