"""Stage 4b: Consolidate family history notes per patient (pre-imputation)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _icd_codes_per_subject(
    merged: pd.DataFrame,
    subject_col: str,
    icd_col: str,
    icd_prefixes: list[str],
) -> pd.DataFrame | None:
    """One row per subject with merged_icd_codes string, or None if no qualifying ICD rows."""
    if icd_col not in merged.columns or not icd_prefixes:
        return None
    pattern = tuple(icd_prefixes)
    cancer_sd_fx = merged[merged[icd_col].astype(str).str.startswith(pattern, na=False)].copy()
    if cancer_sd_fx.empty:
        return None
    grouped = cancer_sd_fx.groupby(subject_col, group_keys=False).apply(
        lambda x: ", ".join(sorted(set(x[icd_col].astype(str))))
    ).reset_index(name="merged_icd_codes")
    return grouped


def run_consolidate_family_history(
    cohort_csv: Path,
    merged_df_csv: Path,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Consolidate FH notes per patient and merge with ICD codes. Returns (dataframe, qc)."""
    fh_cfg = config["family_history"]
    structured_cfg = config.get("structured_data", {})
    subject_col = fh_cfg["subject_id_column"]
    note_col = fh_cfg["note_id_column"]
    icd_col = structured_cfg.get("icd_code_column", "icd_code")
    icd_prefixes = structured_cfg.get("icd_prefixes", ["V16", "Z80"])

    cohort = pd.read_csv(cohort_csv)
    merged = pd.read_csv(merged_df_csv)

    cohort_subjects = set(cohort[subject_col].dropna().unique().tolist())
    merged = merged[merged[subject_col].isin(cohort_subjects)].reset_index(drop=True)

    icd_codes_df = _icd_codes_per_subject(merged, subject_col, icd_col, icd_prefixes)

    cohort_unique = cohort.drop_duplicates(subset=[subject_col, "family_history"]).reset_index(drop=True)

    note_seq_col = "note_seq" if "note_seq" in cohort_unique.columns else None
    if note_seq_col:
        grouped_notes = cohort_unique.groupby(subject_col, group_keys=False).apply(
            lambda x: " ".join(
                x[note_seq_col].astype(str) + "th note: " + x["family_history"].astype(str)
            )
        ).reset_index(name="merged_family_history")
    else:
        grouped_notes = cohort_unique.groupby(subject_col, group_keys=False).apply(
            lambda x: " ".join(x["family_history"].astype(str))
        ).reset_index(name="merged_family_history")

    if icd_codes_df is not None:
        fx_icd_and_notes = grouped_notes.merge(icd_codes_df, on=subject_col, how="left")
    else:
        fx_icd_and_notes = grouped_notes.copy()
        fx_icd_and_notes["merged_icd_codes"] = float("nan")

    patient_demog = merged[[subject_col, "gender", "anchor_age"]].drop_duplicates(subset=subject_col).reset_index(drop=True)
    result = fx_icd_and_notes.merge(patient_demog, on=subject_col, how="left")

    qc = {
        "consolidated_subjects": int(len(result)),
        "subjects_with_icd_codes": int(result["merged_icd_codes"].notna().sum()) if "merged_icd_codes" in result.columns else 0,
    }
    return result, qc
