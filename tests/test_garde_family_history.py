"""Tests for Stage 4d GARDE / FAM-SCAN family history export."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mimic_repro.stages.garde_family_history import (
    GARDE_FAMILY_HISTORY_COLUMNS,
    format_icd_prefix_for_comments,
    run_garde_family_history,
)


def test_format_icd_prefix_empty_and_nan():
    assert format_icd_prefix_for_comments(None) == ""
    assert format_icd_prefix_for_comments(float("nan")) == ""
    assert format_icd_prefix_for_comments(np.nan) == ""
    assert format_icd_prefix_for_comments("") == ""
    assert format_icd_prefix_for_comments("nan") == ""


def test_format_icd_prefix_present():
    assert format_icd_prefix_for_comments("Z803") == "{Z803} "
    assert format_icd_prefix_for_comments("Z803, Z8041") == "{Z803, Z8041} "


def test_run_garde_family_history_16_columns(tmp_path: Path):
    out_csv = tmp_path / "GARDE_family_history.csv"
    merged = tmp_path / "merged.csv"
    pd.DataFrame(
        {
            "subject_id": [100, 101],
            "hadm_id": [1, 2],
            "admittime": ["2020-06-15 10:00:00", "2021-01-01 00:00:00"],
        }
    ).to_csv(merged, index=False)

    df = pd.DataFrame(
        {
            "subject_id": [100, 101],
            "merged_family_history": ["Note A", "Note B"],
            "merged_icd_codes": [float("nan"), "Z80.0"],
            "gender": ["F", "M"],
            "anchor_age": [40, 50],
        }
    )
    cfg = {
        "family_history": {"subject_id_column": "subject_id"},
        "garde": {
            "ehr_pat_id_code_system": "http://epic.com/uhealth/clarity/patient.pat_id",
            "family_history": {"max_length": 5000},
        },
    }
    qc = run_garde_family_history(df, out_csv, cfg, merged_df_csv=merged)["qc"]
    out = pd.read_csv(out_csv)

    assert list(out.columns) == list(GARDE_FAMILY_HISTORY_COLUMNS)
    assert len(out) == 2
    assert qc["schema_columns"] == 16
    c0 = out.iloc[0]["EHR_COMMENTS"]
    assert not str(c0).startswith("{nan}")
    assert c0 == "Note A"
    c1 = out.iloc[1]["EHR_COMMENTS"]
    assert c1.startswith("{Z80.0}")
    assert "Note B" in c1
    assert out.iloc[0]["EHR_REC_DT"] == "2020-06-15"
    assert str(out.iloc[0]["EHR_ENC_ID"]) == "1"
    assert str(out.iloc[0]["EHR_RELATION_CODE"]) == "14"
    assert out.iloc[0]["EHR_RELATION_LABEL"] == "OTHER"
