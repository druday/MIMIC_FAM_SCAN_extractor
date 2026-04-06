# Manuscript Methods Crosswalk

This crosswalk maps the manuscript Methods section to the reproducible pre-LLM pipeline.

## In-Scope (Implemented)

### 1) Data Source & Cohort
- Manuscript: extract Family History from discharge notes; remove non-relevant sections; detect cancer-related mentions.
- Pipeline:
  - `extract_family_history_notes` (Stage 1) performs regex extraction, section trimming, and keyword-based cancer mention flags.

### 2) Keyword Cohort Assembly
- Manuscript-adapted strict mode: all keyword-positive subjects are retained for downstream reproducible analysis.
- Pipeline:
  - `build_validated_cohort` (Stage 2) materializes `keyword_positive_cohort.csv` from all keyword-positive subjects/notes.
  - `merge_structured_mimic` (Stage 3) joins admissions/diagnoses/patients for keyword-positive cohort subjects.

### 3) Structured Family History Restriction
- Manuscript: structured FHx from ICD family-history code prefixes (V16/Z80).
- Pipeline:
  - Stage 3 filters `diagnoses_icd` to configured prefixes (`V16`, `Z80` by default), then merges.

## Partially In-Scope (Stage 4)

### 4) LLM imputation (MIMIC_Paper) and downstream reconciliation
- **In this repo:** Stage 4c runs LLM imputation on consolidated free-text (`llm_imputation.py`), configurable model/provider.
- **Downstream reconciliation:** NER + reconciliation are external to this repository and operate on the **16-column** `GARDE_family_history.csv` (see `docs/FAM_SCAN_VALIDATION.md`).

### 5) GARDE exports (demographics + family history CSV)
- **In this repo:** Stage 4a writes `GARDE_demographics.csv`; Stage 4d writes **16-column** `GARDE_family_history.csv` (GARDE demo column order, `EHR_COMMENTS` = narrative + optional ICD prefix). Encounter fields use admissions when available.
- **GARDE execution:** CDS / knowledge modules run outside this repository; comparative Augmented SD vs SD+UD analysis remains a study-specific downstream step.

## Known Deviations and Risk Notes

- Prior notebook workflow can overwrite `merged_df.csv` across notebooks.
- Downstream notebooks include non-deterministic steps (random sampling and LLM temperature-based generation).
- Manual row-level adjustments in downstream notebook are not encoded as generalized rules.
- Strict pipeline intentionally filters cohort earlier than notebook workflow; run-level differences are recorded in `deviation_report.json`.

## Recommendation for Manuscript Submission

Submit the script-based pre-LLM pipeline plus run artifacts (`run_manifest.json`, `qc_summary.json`) as the reproducibility package, and describe downstream reconciliation/GARDE as external dependencies not bundled in the deterministic artifact.

