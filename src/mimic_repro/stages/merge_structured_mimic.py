"""Stage 3: Merge validated cohort with structured MIMIC tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from mimic_repro.quality import require_columns, summarize_frame


def _filter_icd_prefixes(
    df: pd.DataFrame,
    icd_column: str,
    prefixes: list[str],
) -> pd.DataFrame:
    if icd_column not in df.columns:
        return df
    if not prefixes:
        return df
    pattern = tuple(prefixes)
    filtered = df[df[icd_column].astype(str).str.startswith(pattern, na=False)]
    return filtered.reset_index(drop=True)


def _icd_prefix_distribution(
    df: pd.DataFrame,
    icd_column: str,
    prefixes: list[str],
) -> dict[str, int]:
    if icd_column not in df.columns:
        return {}
    icd_text = df[icd_column].astype(str)
    distribution: dict[str, int] = {}
    for prefix in prefixes:
        distribution[prefix] = int(icd_text.str.startswith(prefix, na=False).sum())
    return distribution


def run_merge_structured_mimic(
    validated_notes_csv: Path,
    admissions_csv: Path,
    diagnoses_icd_csv: Path,
    patients_csv: Path,
    output_merged_csv: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Merge admissions + diagnoses + patients for validated cohort subjects."""
    fh_cfg = config["family_history"]
    structured_cfg = config["structured_data"]
    required = config["quality_checks"]["required_structured_columns"]
    subject_col = fh_cfg["subject_id_column"]
    icd_col = structured_cfg["icd_code_column"]

    validated = pd.read_csv(validated_notes_csv)
    subject_ids = validated[subject_col].dropna().unique().tolist()

    admissions = pd.read_csv(admissions_csv)
    diagnoses = pd.read_csv(diagnoses_icd_csv)
    patients = pd.read_csv(patients_csv)

    require_columns(admissions, required["admissions"], "admissions_csv")
    require_columns(diagnoses, required["diagnoses_icd"], "diagnoses_icd_csv")
    require_columns(patients, required["patients"], "patients_csv")

    admissions = admissions[admissions[subject_col].isin(subject_ids)].reset_index(drop=True)
    diagnoses = diagnoses[diagnoses[subject_col].isin(subject_ids)].reset_index(drop=True)
    patients = patients[patients[subject_col].isin(subject_ids)].reset_index(drop=True)

    diagnoses_fhx = _filter_icd_prefixes(
        diagnoses, icd_col, structured_cfg.get("icd_prefixes", [])
    )
    prefixes = structured_cfg.get("icd_prefixes", [])

    merged = admissions.merge(diagnoses_fhx, on=subject_col, how="outer", suffixes=("", "_dx"))
    merged = merged.merge(patients, on=subject_col, how="outer", suffixes=("", "_pt"))
    merged.to_csv(output_merged_csv, index=False)
    diagnoses_all_subjects = int(diagnoses[subject_col].nunique(dropna=True))
    diagnoses_fhx_subjects = int(diagnoses_fhx[subject_col].nunique(dropna=True))
    validated_subjects = int(len(subject_ids))

    return {
        "input_validated_notes_csv": str(validated_notes_csv),
        "input_admissions_csv": str(admissions_csv),
        "input_diagnoses_icd_csv": str(diagnoses_icd_csv),
        "input_patients_csv": str(patients_csv),
        "output_merged_csv": str(output_merged_csv),
        "qc": {
            "admissions_filtered": summarize_frame(admissions, "admissions_filtered", subject_col),
            "diagnoses_filtered_all": summarize_frame(
                diagnoses, "diagnoses_filtered_all", subject_col
            ),
            "diagnoses_filtered_fhx": summarize_frame(
                diagnoses_fhx, "diagnoses_filtered_fhx", subject_col
            ),
            "patients_filtered": summarize_frame(patients, "patients_filtered", subject_col),
            "merged_output": summarize_frame(merged, "merged_output", subject_col),
            "icd_filter_diagnostics": {
                "icd_prefixes": prefixes,
                "diagnoses_rows_before_prefix_filter": int(len(diagnoses)),
                "diagnoses_rows_after_prefix_filter": int(len(diagnoses_fhx)),
                "diagnoses_subjects_before_prefix_filter": diagnoses_all_subjects,
                "diagnoses_subjects_after_prefix_filter": diagnoses_fhx_subjects,
                "subjects_without_fhx_icd_after_filter": validated_subjects - diagnoses_fhx_subjects,
                "icd_prefix_distribution_before_filter": _icd_prefix_distribution(
                    diagnoses, icd_col, prefixes
                ),
                "icd_prefix_distribution_after_filter": _icd_prefix_distribution(
                    diagnoses_fhx, icd_col, prefixes
                ),
            },
        },
    }

