"""
End-to-end pipeline test: synthetic MIMIC-like inputs, export_subset max_patients=10.

Mocks LLM imputation so no OPENAI_API_KEY is required. Validates cohort subsetting
through GARDE output row counts.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from mimic_repro.config import load_config
from mimic_repro.io_utils import write_json
from mimic_repro.pipeline import run_pipeline
from mimic_repro.stages.garde_family_history import GARDE_FAMILY_HISTORY_COLUMNS

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_synthetic_syn_data(syn_dir: Path, n_subjects: int = 15) -> None:
    """Minimal CSVs that satisfy quality_checks and stages 1–3."""
    subjects = list(range(100001, 100001 + n_subjects))
    discharge_rows = []
    for i, sid in enumerate(subjects):
        # Must match family_history extract_regex and keyword filters (breast cancer).
        text = (
            "Family History:\n"
            "Mother has breast cancer history per clinical note.\n\n"
            "Physical Exam:\n"
            "normal."
        )
        discharge_rows.append({"subject_id": sid, "note_id": i + 1, "text": text})
    pd.DataFrame(discharge_rows).to_csv(syn_dir / "discharge.csv", index=False)

    pd.DataFrame(
        {
            "subject_id": subjects,
            "gender": ["F"] * n_subjects,
            "anchor_age": [50 + (i % 5) for i in range(n_subjects)],
        }
    ).to_csv(syn_dir / "patients.csv", index=False)

    pd.DataFrame(
        {
            "subject_id": subjects,
            "hadm_id": [400000 + i for i in range(n_subjects)],
            "admittime": ["2000-01-01"] * n_subjects,
            "dischtime": ["2000-01-02"] * n_subjects,
        }
    ).to_csv(syn_dir / "admissions.csv", index=False)

    pd.DataFrame(
        {
            "subject_id": subjects,
            "hadm_id": [400000 + i for i in range(n_subjects)],
            "seq_num": [1] * n_subjects,
            "icd_code": ["Z80.0"] * n_subjects,
            "icd_version": [10] * n_subjects,
        }
    ).to_csv(syn_dir / "diagnoses_icd.csv", index=False)


def _mock_run_llm_imputation(df, config):
    out = df.copy()
    out["imputed_family_history"] = out["merged_family_history"].astype(str)
    qc = {
        "imputation_skipped": False,
        "imputed_count": len(out),
        "api_success_count": len(out),
        "api_error_count": 0,
        "raw_count": len(out),
        "provider": "mock",
        "placeholders_total_before": 0,
        "placeholders_total_after": 0,
        "rows_with_remaining_placeholders": 0,
        "rows_finish_reason_length": 0,
        "finish_reason_counts": {},
        "imputation_partial": False,
    }
    return out, qc


@pytest.mark.integration
def test_full_pipeline_synthetic_cohort_size_10(tmp_path: Path) -> None:
    syn = tmp_path / "syn"
    syn.mkdir()
    n_cohort = 15
    _write_synthetic_syn_data(syn, n_subjects=n_cohort)

    cfg = load_config(REPO_ROOT / "config/pre_llm_config.json")
    cfg["paths"]["discharge_csv"] = "syn/discharge.csv"
    cfg["paths"]["admissions_csv"] = "syn/admissions.csv"
    cfg["paths"]["diagnoses_icd_csv"] = "syn/diagnoses_icd.csv"
    cfg["paths"]["patients_csv"] = "syn/patients.csv"
    cfg["paths"]["artifacts_root"] = "artifacts/pre_llm"
    cfg["export_subset"] = {
        "enabled": True,
        "max_patients": 10,
        "age_min": None,
        "age_max": None,
        "records_per_patient_min": None,
        "records_per_patient_max": None,
        "random_seed": 42,
    }
    cfg["garde_export"] = {"enabled": True}

    config_path = tmp_path / "config" / "e2e.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(config_path, cfg)

    with patch("mimic_repro.pipeline.run_llm_imputation", side_effect=_mock_run_llm_imputation):
        run_dir = run_pipeline(config_path=config_path, run_name="e2e_subset10")

    qc = json.loads((run_dir / "qc_summary.json").read_text(encoding="utf-8"))

    assert "stage4_subset" in qc
    assert qc["stage4_subset"]["subjects_before"] == n_cohort
    assert qc["stage4_subset"]["subjects_after"] == 10
    assert qc["stage4_subset"]["filters_applied"]["max_patients"] == 10

    assert (run_dir / "keyword_positive_cohort_subset.csv").exists()
    assert (run_dir / "merged_df_subset.csv").exists()

    cohort_sub = pd.read_csv(run_dir / "keyword_positive_cohort_subset.csv")
    assert cohort_sub["subject_id"].nunique() == 10

    demo = pd.read_csv(run_dir / "GARDE_demographics.csv")
    assert len(demo) == 10
    assert demo["EHR_PAT_ID"].nunique() == 10

    fh = pd.read_csv(run_dir / "GARDE_family_history.csv")
    # One GARDE row per patient (consolidated family history).
    assert len(fh) == 10
    assert fh["EHR_PAT_ID"].nunique() == 10
    assert list(fh.columns) == list(GARDE_FAMILY_HISTORY_COLUMNS)
    assert qc["stage4d_garde_family_history"]["schema_columns"] == 16
    assert (fh["EHR_REC_ID"] == 1).all()
    # No literal {nan} in comments from ICD prefix
    bad = fh["EHR_COMMENTS"].astype(str).str.contains(r"\{nan\}", case=False, regex=True)
    assert not bad.any()

    stage4c = qc.get("stage4c_llm_imputation", {})
    assert stage4c.get("provider") == "mock"
    assert stage4c.get("imputed_count") == 10
