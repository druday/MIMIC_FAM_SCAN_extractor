# FAM-SCAN validation (after MIMIC export)

`GARDE_family_history.csv` from this pipeline is a **16-column** file aligned with the **GARDE** demo family-history shape (`ut-DE-ID-pat-fhx`). It is intended as input to a downstream reconciliation step before GARDE evaluation.

## Contract

- Column names and order are defined in code as `GARDE_FAMILY_HISTORY_COLUMNS` in [`src/mimic_repro/stages/garde_family_history.py`](../src/mimic_repro/stages/garde_family_history.py).
- **Row granularity:** **one row per patient** (consolidated family history). `GARDE_demographics.csv` stays **one row per patient**.
- **`EHR_REC_ID`:** always **`1`** (single consolidated record per patient).
- Narrative text (with optional ICD prefix when structured ICDs exist) lives in **`EHR_COMMENTS`**.
- **`EHR_COND_*` / `EHR_RELATION_*`:** configurable **placeholders** for FAM-SCAN’s structured line (not clinical truth until reconciliation); see README.
- **`EHR_PAT_ID`** is MIMIC `subject_id` (not Epic de-identified UUIDs).
- **`EHR_FAMILY_HX_ID`** is a deterministic UUID (v5) from patient id + `EHR_REC_ID` (stable one id per patient).
- **`EHR_ENC_ID`** / **`EHR_REC_DT`** use the first `hadm_id` / `admittime` per subject from merged admissions when attached to the export row.

## Smoke test against downstream reconciliation

1. Start your downstream reconciliation service that accepts the 16-column GARDE-compatible family-history CSV.

2. POST the exported CSV:

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/epic-fam-scan-csv" \
  -F "file=@artifacts/pre_llm/<run_id>/GARDE_family_history.csv" \
  -o /tmp/fam_scan_out.csv
```

3. If your downstream service requires a different family-history CSV contract, update either that service or this repo’s `GARDE_FAMILY_HISTORY_COLUMNS` so they match, then re-run the curl test.

4. For aggregate QA (validated dataset), use:

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/epic-fam-scan-validation" \
  -F "file=@artifacts/pre_llm/<run_id>/GARDE_family_history.csv" \
  -o /tmp/fam_scan_validation.csv
```

## GARDE handoff

Place demographics + processed family history into your GARDE deployment’s input directory. Confirm column order with the GARDE importer; if it expects the raw demo header order, it should match this export.
