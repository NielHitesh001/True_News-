# Milestone 8 Walkthrough: Continuous & Multi-Event Pipeline

## Overview
Milestone 8 implements the dynamic updating, versioning, and continuous event lifecycle engine. It handles incremental article ingestion, real-time confidence tier upgrades (Tier 3 &rarr; Tier 2 &rarr; Tier 1), publisher retraction propagation, and automated brief version diffing.

---

## Key Modules Built

### 1. Incremental Event Matcher (`newsx.continuous.EventMatcher`)
- Calculates token and entity overlap between incoming candidate articles and active events.
- Routes follow-up coverage directly to the matching event without re-clustering unrelated events.

### 2. Continuous Engine (`newsx.continuous.ContinuousEngine`)
- **Incremental Event Updating**: Ingests new articles, updates event member lists, and re-corroborates claims.
- **Dynamic Confidence Transitions**:
  - **Tier 3 &rarr; Tier 2**: Upgrades single-source claims when a second independent secondary origin corroborates the fact.
  - **Tier 2 &rarr; Tier 1**: Upgrades claims to Primary Confirmed upon arrival of official agency filings (e.g., NTSB report).
  - **Contradiction Emergence**: Downgrades conflicting propositions to **Tier 4 (Disputed)** and formats side-by-side comparisons.
- **Publisher Retraction & Correction Engine**:
  - Automatically rejects affected claims (`ClaimStatus.REJECTED`).
  - Purges retracted statements from cluster consensus.
  - Recalculates event confidence tiers and logs retractions in `version_history` and `audit_log`.
- **Structured Brief Diffing (`BriefDiff`)**:
  - Computes exact diffs between successive brief versions ($v1.0 \rightarrow v1.1$), capturing new core facts, promoted tiers, new disputes, and retracted claims.

---

## Verification & Benchmark Results

### Full Test Suite (66 tests passed)
```
PYTHONPATH=src:. .venv/bin/python -m pytest tests/ -v
============================== 66 passed in 1.21s ==============================
```

### Benchmark Simulation (`scripts/evaluate_continuous.py`)
- Evaluated multi-wave event timeline simulation:
  - **Wave 1 (Breaking)**: Initial Reuters dispatch established baseline single-source claims.
  - **Wave 2 (Corroboration)**: Associated Press dispatch matched to event; elevated claims to Tier 2.
  - **Wave 3 (Primary Confirmation)**: NTSB preliminary report elevated claims to Tier 1.
  - **Wave 4 (Contested Dispute)**: Conflicting maritime reports on Second Thomas Shoal isolated into Disputed Points.
  - **Wave 5 (Retraction)**: Fabricated rumor retracted; affected claims purged from event brief.
