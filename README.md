# Reproducible Pre-LLM MIMIC Pipeline

This repository now includes a script-first, deterministic pipeline that reproduces the **pre-LLM cohort and data assembly** portions of the manuscript workflow.

The pipeline covers logic previously implemented in:
- `Final 1 Family History Notes from MIMIC-Note.ipynb`
- `Final 2 Family History Data from MIMIC-IV.ipynb`

Stage 4 runs **LLM imputation** (optional API key) and exports **GARDE-shaped** demographics and a **16-column** `GARDE_family_history.csv` for downstream reconciliation and GARDE evaluation. See [docs/FAM_SCAN_VALIDATION.md](docs/FAM_SCAN_VALIDATION.md) and `docs/methods_crosswalk.md`.

## What The Pipeline Produces

For each run, the pipeline writes a versioned directory under `artifacts/pre_llm/`:

- `family_history_notes_extracted.csv`
- `family_history_keyword_positive.csv`
- `keyword_positive_cohort.csv`
- `merged_df.csv`
- `qc_summary.json`
- `run_manifest.json`
- `deviation_report.json`

When `garde_export.enabled` is true (see `config/pre_llm_config.json`), Stage 4 also writes:

- `GARDE_demographics.csv` — Epic-style demographics row per patient.
- `GARDE_family_history.csv` — **16 columns** (GARDE demo / FAM-SCAN contract): **one row per patient** (consolidated family history after LLM imputation). `EHR_REC_ID` is always `1`. Narrative + optional ICD list in `EHR_COMMENTS`; deterministic UUID `EHR_FAMILY_HX_ID` per patient; encounter fields from the first `hadm_id` / `admittime` per subject from merged admissions when not already on the consolidated row. Code systems and synthetic SD placeholders (`EHR_COND_*`, `EHR_RELATION_*`) are under `garde.family_history`.

**Downstream flow:** this repository produces GARDE-compatible exports that can be handed to downstream reconciliation and GARDE evaluation workflows. The downstream services are not bundled in this repository; see [docs/FAM_SCAN_VALIDATION.md](docs/FAM_SCAN_VALIDATION.md) for the contract this app emits.

## Environment Setup

1. Use Python 3.12+.
2. Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run The Pipeline

### Option A: Makefile

```bash
make pre_llm_pipeline
```

Optional deterministic run folder name:

```bash
make pre_llm_pipeline RUN_NAME=run_mimic_prellm_v1
```

### Option B: Python module directly

```bash
PYTHONPATH=src python3 -m mimic_repro.pipeline --config config/pre_llm_config.json
```

## Input Requirements

Required input files are configured in `config/pre_llm_config.json`. See `docs/data_access_contract.md` for expected columns.

## Reproducibility and Provenance

Each run emits:
- `qc_summary.json` with row counts, key null percentages, duplicate checks, lineage and ICD diagnostics.
- `run_manifest.json` with:
  - input/output checksums,
  - input/output row counts,
  - config checksum,
  - runtime metadata (Python/platform/git commit when available).
- `deviation_report.json` with strict output comparison against notebook-visible metrics.

## Methods Alignment

Manuscript-to-pipeline alignment and explicit downstream dependencies are documented in:
- `docs/methods_crosswalk.md`
- `docs/strict_vs_notebook_counts.md`
- `docs/keyword_and_extraction_audit.md`

## Testing

```bash
pytest tests/
```

- **`tests/test_pipeline_e2e_synthetic.py`** runs the **full pipeline** (stages 1–4) on **synthetic** MIMIC-like CSVs in a temp directory with **`export_subset.max_patients: 10`**, asserting **10** subjects in GARDE outputs. LLM imputation is **mocked** (no `OPENAI_API_KEY` required).

## Operator Console (React)

This repo now includes an operator UI for stage-by-stage execution:
- Backend API: `backend_api/main.py`
- Frontend: `frontend/`
- Guide: `docs/operator_console.md`

Run locally:
- `make api_dev`
- `cd frontend && npm install && npm run dev`

