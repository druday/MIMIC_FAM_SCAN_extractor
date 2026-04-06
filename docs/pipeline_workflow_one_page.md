# FAM-SCAN MIMIC Pipeline: One-Page Workflow

**Goal:** Run a fresh pipeline (Path A) to produce GARDE-ready CSVs (demographics + family history), then validate outputs with human review.

---

## End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  RAW MIMIC DATA                                                                          │
│  • discharge.csv (notes)  • admissions.csv  • diagnoses_icd.csv  • patients.csv         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: PRE-LLM PIPELINE (Path A — keyword-positive cohort)                           │
│  ─────────────────────────────────────────────────────────────────────────────────────  │
│  Stage 1  Extract FH section → trim at Physical Exam → flag cancer keywords             │
│           Output: family_history_notes_extracted.csv, family_history_keyword_positive.csv│
│                                                                                         │
│  Stage 2  Build cohort from keyword-positive notes (optional refiners: gender, age,      │
│           cancer type, note length, notes/patient)                                       │
│           Output: keyword_positive_cohort.csv                                            │
│                                                                                         │
│  Stage 3  Merge structured MIMIC (admissions + diagnoses[V16/Z80] + patients)            │
│           Output: merged_df.csv                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: GARDE EXPORT (to be integrated)                                               │
│  ─────────────────────────────────────────────────────────────────────────────────────  │
│  Stage 4a  Demographics CSV (Notebook 3 logic)                                          │
│            • Group merged_df by subject_id (mode for categoricals)                      │
│            • Generate DOB from anchor_age, map gender/religion to GARDE codes            │
│            • Output: GARDE_demographics.csv                                             │
│                                                                                         │
│  Stage 4b  Family History CSV                                                           │
│            • Group FH notes per patient (from keyword_positive_cohort)                   │
│            • Optionally merge ICD codes (V16/Z80) per patient                            │
│            • Optional: LLM imputation of ___ placeholders (Notebook 4)                   │
│            • Output: GARDE_family_history.csv                                           │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: HUMAN VALIDATION                                                              │
│  ─────────────────────────────────────────────────────────────────────────────────────  │
│  • Review cohort size and composition (subjects, notes, cancer-type distribution)       │
│  • Spot-check FH text quality, extraction accuracy, keyword relevance                   │
│  • Validate demographics mapping (gender, age, religion)                                │
│  • Decide: accept for GARDE run, or refine cohort (adjust refiners) and re-run           │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Status

| Phase | Stage | Status | Source |
|-------|-------|--------|--------|
| 1 | Stage 1–3 | **Implemented** | `src/mimic_repro/`, operator console |
| 2 | Stage 4a Demographics | **Implemented** | `garde_demographics.py` |
| 2 | Stage 4b–4d FH + LLM + Export | **Implemented** | `consolidate_family_history.py` (consolidate per patient + ICD), `llm_imputation.py`, `garde_family_history.py` (one CSV row per patient) |
| 3 | Human validation | **Process** | Fresh look recommended |

---

## Key Outputs

| Output | Description |
|--------|-------------|
| `keyword_positive_cohort.csv` | FH notes for cohort (subject_id, note_id, family_history, cancer flags) |
| `merged_df.csv` | Structured MIMIC joined by subject_id |
| `GARDE_demographics.csv` | Patient ID, DOB, sex, religion (GARDE format) |
| `GARDE_family_history.csv` | Patient ID + consolidated FH text (and optionally ICD codes) |

---

## Decisions for Next Steps

1. **GARDE FH format:** Confirm exact schema GARDE expects for family history (columns, structure).
2. **Determinism:** Notebook 3 uses random DOB and random religion. Decide: seed for reproducibility, or accept non-determinism for GARDE run.
3. **LLM imputation:** Notebook 4 imputes `___` via Azure OpenAI. Include before GARDE, or feed raw text?
4. **Validation workflow:** Define checklist (what to review, sample size, pass/fail criteria) and where to record results.

---

## Notebook Coverage

| Notebook | Content | Pipeline Coverage |
|----------|---------|-------------------|
| Final 1 | FH extraction, keywords, structured merge | Stages 1–3 ✓ |
| Final 2 | Structured merge for cohort | Stage 3 ✓ |
| Final 3 | GARDE demographics | Stage 4a — to add |
| Final 4 | ICD grouping, note grouping, LLM imputation, length filter | Stage 4b — to add |
