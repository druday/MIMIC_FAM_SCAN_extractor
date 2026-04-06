"""Tests for pre-stage-4 cohort subsetting (max_patients and filters)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mimic_repro.stages.export_subset import _coerce_max_patients, run_export_subset


@pytest.fixture
def minimal_config() -> dict:
    return {
        "family_history": {"subject_id_column": "subject_id"},
        "export_subset": {
            "enabled": True,
            "max_patients": 10,
            "age_min": None,
            "age_max": None,
            "records_per_patient_min": None,
            "records_per_patient_max": None,
            "random_seed": 42,
        },
    }


def test_coerce_max_patients_accepts_string_and_float():
    assert _coerce_max_patients("10") == 10
    assert _coerce_max_patients(10.0) == 10
    assert _coerce_max_patients(None, default=250) == 250
    assert _coerce_max_patients(-3) == 250
    assert _coerce_max_patients("not-a-number") == 250


def test_run_export_subset_caps_unique_subjects_to_max_patients(tmp_path: Path, minimal_config: dict):
    """With 40 eligible subjects and max_patients=10, outputs must contain exactly 10 subjects."""
    n_subjects = 40
    rows_per = 2
    cohort_rows = []
    merged_rows = []
    for sid in range(n_subjects):
        cohort_rows.append({"subject_id": sid, "family_history": f"note for {sid}"})
        for r in range(rows_per):
            merged_rows.append(
                {
                    "subject_id": sid,
                    "anchor_age": 50.0,
                    "gender": "F",
                    "hadm_id": sid * 100 + r,
                }
            )

    cohort_csv = tmp_path / "cohort.csv"
    merged_csv = tmp_path / "merged.csv"
    out_cohort = tmp_path / "cohort_sub.csv"
    out_merged = tmp_path / "merged_sub.csv"

    pd.DataFrame(cohort_rows).to_csv(cohort_csv, index=False)
    pd.DataFrame(merged_rows).to_csv(merged_csv, index=False)

    qc = run_export_subset(
        cohort_csv=cohort_csv,
        merged_df_csv=merged_csv,
        output_cohort_subset_csv=out_cohort,
        output_merged_subset_csv=out_merged,
        config=minimal_config,
    )

    sub_cohort = pd.read_csv(out_cohort)
    sub_merged = pd.read_csv(out_merged)
    n_out = sub_cohort["subject_id"].nunique()

    assert n_out == 10, f"expected 10 subjects in subset, got {n_out}"
    assert sub_merged["subject_id"].nunique() == 10
    assert qc["subjects_before"] == n_subjects
    assert qc["subjects_after"] == 10
    assert qc["filters_applied"]["max_patients"] == 10


def test_run_export_subset_keeps_all_subjects_when_under_cap(tmp_path: Path, minimal_config: dict):
    minimal_config["export_subset"]["max_patients"] = 100
    cohort_rows = [{"subject_id": i, "family_history": "x"} for i in range(5)]
    merged_rows = [{"subject_id": i % 5, "anchor_age": 40.0} for i in range(10)]

    cohort_csv = tmp_path / "c.csv"
    merged_csv = tmp_path / "m.csv"
    pd.DataFrame(cohort_rows).to_csv(cohort_csv, index=False)
    pd.DataFrame(merged_rows).to_csv(merged_csv, index=False)

    qc = run_export_subset(
        cohort_csv=cohort_csv,
        merged_df_csv=merged_csv,
        output_cohort_subset_csv=tmp_path / "cs.csv",
        output_merged_subset_csv=tmp_path / "ms.csv",
        config=minimal_config,
    )
    assert qc["subjects_after"] == 5
