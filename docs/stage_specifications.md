# Stage Specifications (Notebook 1-2 Codification)

This document codifies notebook logic as explicit, reproducible pipeline stages.

## Stage 1: `extract_family_history_notes`

### Inputs
- `MIMIC Data/mimic-iv-note-deidentified-free-text-clinical-notes-2.2/note/discharge.csv`

### Core logic
- Extract `Family History` section using regex:
  - `Family History:\n(.*?)\n\n`
- Remove rows where family history extraction is null.
- Trim text after configured headers (`Physical Exam:` by default).
- Apply keyword-based mention flags for:
  - breast cancer indicators,
  - ovarian cancer indicators,
  - colorectal cancer indicators.
- Build `any_cancer_keyword_mention` as OR across the three categories.

### Outputs
- `family_history_notes_extracted.csv` (all extracted FH notes)
- `family_history_keyword_positive.csv` (keyword-positive subset)
- QC includes keyword-list audit and subject drop-off (`extracted_subjects` -> `keyword_positive_subjects`).

---

## Stage 2: `build_validated_cohort`

### Inputs
- `family_history_keyword_positive.csv` (from Stage 1)

### Core logic
- Include **all keyword-positive subjects** and **all keyword-positive notes**.
- Optionally apply deterministic patient-level refiners:
  - `gender`
  - `anchor_age` range
  - note length range (`family_history` character length)
  - notes-per-patient range
  - cancer-type inclusion (`breast`, `ovarian`, `colorectal`) based on Stage 1 mention flags.
- Sort output by `subject_id`, `note_id`.

### Output
- `keyword_positive_cohort.csv`

---

## Stage 3: `merge_structured_mimic`

### Inputs
- `keyword_positive_cohort.csv` (from Stage 2)
- `MIMIC Data/mimic-iv-2.2/hosp/admissions.csv`
- `MIMIC Data/mimic-iv-2.2/hosp/diagnoses_icd.csv`
- `MIMIC Data/mimic-iv-2.2/hosp/patients.csv`

### Core logic
- Filter each structured table to `subject_id` values in keyword-positive cohort.
- Restrict diagnoses to configured family-history ICD prefixes (`V16`, `Z80` by default).
- Outer merge by `subject_id`:
  - admissions + filtered diagnoses + patients.
- Emit ICD diagnostics:
  - rows/subjects before and after prefix filter,
  - subjects without retained FHx ICD codes,
  - per-prefix row distribution.

### Output
- `merged_df.csv`

---

## Cross-Stage Data Flow

1. Stage 1 creates extracted and cancer-keyword-positive note subsets.
2. Stage 2 materializes the keyword-positive cohort note file used by structured merge.
3. Stage 3 produces manuscript-aligned structured+unstructured join artifact for pre-LLM work.

