# Data Access Contract (Pre-LLM Pipeline)

## Required Input Files

- `MIMIC Data/mimic-iv-note-deidentified-free-text-clinical-notes-2.2/note/discharge.csv`
- `MIMIC Data/mimic-iv-2.2/hosp/admissions.csv`
- `MIMIC Data/mimic-iv-2.2/hosp/diagnoses_icd.csv`
- `MIMIC Data/mimic-iv-2.2/hosp/patients.csv`

## Required Columns

### Discharge notes
- `subject_id`
- `note_id`
- `text`

### Admissions
- `subject_id`

### Diagnoses ICD
- `subject_id`
- `icd_code`

### Patients
- `subject_id`
- `gender`
- `anchor_age`

## Configuration-Driven Fields

The following are controlled via `config/pre_llm_config.json`:
- Regex extraction pattern for family history text.
- Delimiter headers used to trim family history content.
- Keyword dictionaries for breast/ovarian/colorectal signals.
- ICD family-history code prefixes (default `V16`, `Z80`).
- Strict cohort source (default: keyword-positive extracted notes).
- Optional deterministic cohort refiners:
  - `cohort.refiners.enabled`
  - `cohort.refiners.genders`
  - `cohort.refiners.age_min` / `age_max`
  - `cohort.refiners.note_length_min` / `note_length_max`
  - `cohort.refiners.notes_per_patient_min` / `notes_per_patient_max`
  - `cohort.refiners.cancer_types`

## Data Access and Credentials

- Access to MIMIC-IV and MIMIC-IV-Note is required.
- This pipeline assumes local CSV exports are already available at configured paths.
- No external API credentials are needed for this pre-LLM pipeline.

