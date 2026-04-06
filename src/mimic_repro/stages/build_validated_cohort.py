"""Stage 2: Build keyword-positive cohort for downstream processing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from mimic_repro.quality import summarize_frame


def run_build_validated_cohort(
    keyword_positive_notes_csv: Path,
    patients_csv: Path,
    output_keyword_positive_cohort_csv: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Create a deterministic refined subset from keyword-positive cohort."""
    fh_cfg = config["family_history"]
    refined_cfg = config.get("cohort", {}).get("refiners", {})
    refiner_enabled = bool(refined_cfg.get("enabled", False))

    notes_df = pd.read_csv(keyword_positive_notes_csv)
    patients_df = pd.read_csv(patients_csv)

    subject_col = fh_cfg["subject_id_column"]
    note_col = fh_cfg["note_id_column"]
    cohort_cfg = config.get("cohort", {})
    keyword_positive_subjects = int(notes_df[subject_col].nunique(dropna=True))
    keyword_positive_notes = int(len(notes_df))

    cohort_df = notes_df.copy()
    if refiner_enabled:
        patient_cols = [subject_col, "gender", "anchor_age"]
        available_cols = [c for c in patient_cols if c in patients_df.columns]
        patient_view = patients_df[available_cols].drop_duplicates(subset=[subject_col])
        cohort_df = cohort_df.merge(patient_view, on=subject_col, how="left")

        genders = refined_cfg.get("genders", [])
        if isinstance(genders, list) and genders:
            cohort_df = cohort_df[cohort_df["gender"].isin(genders)]

        age_min = refined_cfg.get("age_min")
        age_max = refined_cfg.get("age_max")
        if age_min is not None:
            cohort_df = cohort_df[cohort_df["anchor_age"] >= float(age_min)]
        if age_max is not None:
            cohort_df = cohort_df[cohort_df["anchor_age"] <= float(age_max)]

        note_length_min = refined_cfg.get("note_length_min")
        note_length_max = refined_cfg.get("note_length_max")
        if "family_history" in cohort_df.columns:
            note_length = cohort_df["family_history"].astype(str).str.len()
            if note_length_min is not None:
                cohort_df = cohort_df[note_length >= int(note_length_min)]
                note_length = cohort_df["family_history"].astype(str).str.len()
            if note_length_max is not None:
                cohort_df = cohort_df[note_length <= int(note_length_max)]

        # Cancer type filtering is applied at subject-level for deterministic retention.
        cancer_types = refined_cfg.get("cancer_types", [])
        type_to_flag = {
            "breast": "breast_cancer_mention",
            "ovarian": "ovarian_cancer_mention",
            "colorectal": "colorectal_cancer_mention",
        }
        selected_flags = [type_to_flag[t] for t in cancer_types if t in type_to_flag]
        if selected_flags:
            subject_flags = (
                cohort_df.groupby(subject_col)[selected_flags]
                .max(numeric_only=True)
                .reset_index()
            )
            subject_flags["selected_cancer_hit"] = subject_flags[selected_flags].any(axis=1)
            keep_subjects = set(
                subject_flags.loc[subject_flags["selected_cancer_hit"], subject_col].tolist()
            )
            cohort_df = cohort_df[cohort_df[subject_col].isin(keep_subjects)]

        notes_per_patient_min = refined_cfg.get("notes_per_patient_min")
        notes_per_patient_max = refined_cfg.get("notes_per_patient_max")
        if notes_per_patient_min is not None or notes_per_patient_max is not None:
            counts = cohort_df.groupby(subject_col)[note_col].count().reset_index(name="note_count")
            if notes_per_patient_min is not None:
                counts = counts[counts["note_count"] >= int(notes_per_patient_min)]
            if notes_per_patient_max is not None:
                counts = counts[counts["note_count"] <= int(notes_per_patient_max)]
            keep_subjects = set(counts[subject_col].tolist())
            cohort_df = cohort_df[cohort_df[subject_col].isin(keep_subjects)]

    cohort_df = cohort_df.sort_values(by=[subject_col, note_col]).reset_index(drop=True)
    cohort_df.to_csv(output_keyword_positive_cohort_csv, index=False)

    notes_per_subject = (
        float(cohort_df.groupby(subject_col)[note_col].count().mean())
        if not cohort_df.empty
        else 0.0
    )
    notes_per_patient_stats = (
        cohort_df.groupby(subject_col)[note_col].count() if not cohort_df.empty else pd.Series(dtype=float)
    )
    note_lengths = (
        cohort_df["family_history"].astype(str).str.len()
        if not cohort_df.empty and "family_history" in cohort_df.columns
        else pd.Series(dtype=float)
    )

    return {
        "input_keyword_positive_notes_csv": str(keyword_positive_notes_csv),
        "input_patients_csv": str(patients_csv),
        "output_keyword_positive_cohort_csv": str(output_keyword_positive_cohort_csv),
        "qc": {
            "keyword_positive_cohort": summarize_frame(
                cohort_df,
                "keyword_positive_cohort",
                subject_id_col=subject_col,
                duplicate_keys=[note_col],
            ),
            "notes_per_subject_avg": round(notes_per_subject, 2),
            "strict_cohort_assumptions": {
                "cohort_source": cohort_cfg.get("strict_cohort_source", "keyword_positive_notes"),
                "refiners_enabled": refiner_enabled,
                "refiners": refined_cfg,
                "selection_rule": "deterministic_patient_level_refinement_then_note_subset",
            },
            "lineage": {
                "keyword_positive_notes": keyword_positive_notes,
                "keyword_positive_subjects": keyword_positive_subjects,
                "final_family_history_records": int(len(cohort_df)),
                "final_strict_subjects": int(cohort_df[subject_col].nunique(dropna=True)),
                "final_notes_per_patient_min": int(notes_per_patient_stats.min())
                if not notes_per_patient_stats.empty
                else 0,
                "final_notes_per_patient_max": int(notes_per_patient_stats.max())
                if not notes_per_patient_stats.empty
                else 0,
                "final_note_length_min": int(note_lengths.min()) if not note_lengths.empty else 0,
                "final_note_length_max": int(note_lengths.max()) if not note_lengths.empty else 0,
            },
        },
    }

