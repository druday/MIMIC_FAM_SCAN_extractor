"""Pre-Stage 4: Filter and subset cohort before GARDE export (reduces LLM imputation cost)."""

from __future__ import annotations

import numpy as np
from pathlib import Path
from typing import Any

import pandas as pd


def _coerce_max_patients(raw: Any, *, default: int = 250) -> int:
    """Parse max_patients from config (int, float, or numeric string)."""
    if raw is None:
        return default
    try:
        n = int(float(raw))
    except (TypeError, ValueError):
        return default
    return n if n > 0 else default


def run_export_subset(
    cohort_csv: Path,
    merged_df_csv: Path,
    output_cohort_subset_csv: Path,
    output_merged_subset_csv: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Filter and limit cohort; write subset files for Stage 4. Returns QC dict."""
    fh_cfg = config["family_history"]
    subset_cfg = config.get("export_subset", {})
    subject_col = fh_cfg["subject_id_column"]

    cohort = pd.read_csv(cohort_csv)
    merged = pd.read_csv(merged_df_csv)

    cohort_subjects = set(cohort[subject_col].dropna().unique().tolist())
    merged = merged[merged[subject_col].isin(cohort_subjects)].reset_index(drop=True)

    subjects_before = int(len(cohort_subjects))

    records_per_subject = merged.groupby(subject_col).size().reset_index(name="_record_count")
    subject_meta = merged[[subject_col]].drop_duplicates()
    if "anchor_age" in merged.columns:
        age_per_subject = merged.groupby(subject_col)["anchor_age"].max().reset_index(name="anchor_age")
        subject_meta = subject_meta.merge(age_per_subject, on=subject_col, how="left")
    subject_meta = subject_meta.merge(records_per_subject, on=subject_col, how="left")

    age_min = subset_cfg.get("age_min")
    age_max = subset_cfg.get("age_max")
    if age_min is not None and "anchor_age" in subject_meta.columns:
        subject_meta = subject_meta[subject_meta["anchor_age"] >= float(age_min)]
    if age_max is not None and "anchor_age" in subject_meta.columns:
        subject_meta = subject_meta[subject_meta["anchor_age"] <= float(age_max)]

    rec_min = subset_cfg.get("records_per_patient_min")
    rec_max = subset_cfg.get("records_per_patient_max")
    if rec_min is not None:
        subject_meta = subject_meta[subject_meta["_record_count"] >= int(rec_min)]
    if rec_max is not None:
        subject_meta = subject_meta[subject_meta["_record_count"] <= int(rec_max)]

    eligible_subjects = subject_meta[subject_col].dropna().unique().tolist()
    max_patients = _coerce_max_patients(subset_cfg.get("max_patients", 250))
    random_seed = int(subset_cfg.get("random_seed", 42))

    if len(eligible_subjects) <= max_patients:
        selected_subjects = eligible_subjects
    else:
        rng = np.random.default_rng(seed=random_seed)
        perm = rng.permutation(len(eligible_subjects))
        selected_subjects = [eligible_subjects[i] for i in perm[:max_patients]]

    selected_set = set(selected_subjects)
    cohort_subset = cohort[cohort[subject_col].isin(selected_set)].reset_index(drop=True)
    merged_subset = merged[merged[subject_col].isin(selected_set)].reset_index(drop=True)

    cohort_subset.to_csv(output_cohort_subset_csv, index=False)
    merged_subset.to_csv(output_merged_subset_csv, index=False)

    subjects_after = int(len(selected_subjects))

    qc = {
        "subjects_before": subjects_before,
        "subjects_after": subjects_after,
        "filters_applied": {
            "age_min": age_min,
            "age_max": age_max,
            "records_per_patient_min": rec_min,
            "records_per_patient_max": rec_max,
            "max_patients": max_patients,
            "random_seed": random_seed,
        },
    }
    return qc
