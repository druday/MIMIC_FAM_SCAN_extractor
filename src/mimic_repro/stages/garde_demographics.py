"""Stage 4a: GARDE demographics CSV generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _mode_func(series: pd.Series) -> Any:
    modes = series.mode()
    return modes.iloc[0] if not modes.empty else None


def _random_dob_from_age(age: float, current_year: int) -> pd.Timestamp:
    birth_year = int(current_year - age)
    start_date = pd.Timestamp(year=birth_year, month=1, day=1)
    end_date = pd.Timestamp(year=birth_year, month=12, day=31)
    days_range = (end_date - start_date).days
    random_offset = np.random.randint(0, days_range + 1)
    return start_date + pd.Timedelta(days=random_offset)


def _assign_religion_code(
    df: pd.DataFrame,
    label_to_code: dict[str, float],
    label_col: str = "EHR_RELIGION_LABEL",
    new_col: str = "EHR_RELIGION_CODE",
) -> pd.DataFrame:
    df = df.copy()
    df[new_col] = df[label_col].map(label_to_code)
    return df


def run_garde_demographics(
    merged_df_csv: Path,
    cohort_csv: Path,
    output_garde_demographics_csv: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Generate GARDE demographics CSV from merged MIMIC data."""
    fh_cfg = config["family_history"]
    garde_cfg = config.get("garde", {})
    religion_cfg = config.get("religion", {})

    subject_col = fh_cfg["subject_id_column"]

    merged = pd.read_csv(merged_df_csv)
    cohort = pd.read_csv(cohort_csv)
    cohort_subjects = set(cohort[subject_col].dropna().unique().tolist())
    merged = merged[merged[subject_col].isin(cohort_subjects)].reset_index(drop=True)

    if merged.empty:
        empty_df = pd.DataFrame(
            columns=[
                "EHR_PAT_ID_CODE_SYSTEM",
                "EHR_PAT_ID",
                "BIRTH_DATE",
                "EHR_SEX_CODE_SYSTEM",
                "EHR_SEX_CODE",
                "EHR_SEX_LABEL",
                "EHR_RELIGION_CODE_SYSTEM",
                "EHR_RELIGION_CODE",
                "EHR_RELIGION_LABEL",
                "PREV_MET_CRITERIA_LIST",
            ]
        )
        empty_df.to_csv(output_garde_demographics_csv, index=False)
        return {
            "output_garde_demographics_csv": str(output_garde_demographics_csv),
            "qc": {"demographics_rows": 0, "demographics_subjects": 0},
        }

    agg_dict: dict[str, Any] = {}
    if "hadm_id" in merged.columns:
        agg_dict["total_visits"] = ("hadm_id", "nunique")
    if "gender" in merged.columns:
        agg_dict["gender"] = ("gender", _mode_func)
    if "anchor_age" in merged.columns:
        agg_dict["anchor_age_min"] = ("anchor_age", "min")
        agg_dict["anchor_age_max"] = ("anchor_age", "max")
    for col in ["admission_type", "discharge_location", "language", "marital_status", "race", "anchor_year", "anchor_year_group", "dod"]:
        if col in merged.columns:
            agg_dict[col] = (col, _mode_func)

    summary = merged.groupby(subject_col).agg(**agg_dict).reset_index()

    if "anchor_age_max" not in summary.columns:
        summary["anchor_age_max"] = summary.get("anchor_age_min", 0)

    current_year = pd.Timestamp.today().year
    summary["anchor_age_generated_dob"] = summary["anchor_age_max"].apply(
        lambda a: _random_dob_from_age(float(a), current_year)
    )

    gender_col = "gender" if "gender" in summary.columns else None
    if gender_col:
        summary["gender_generated_label"] = summary[gender_col].replace({"F": "Female", "M": "Male"})
        summary["gender_generated_code"] = summary[gender_col].map({"F": 1, "M": 2}).astype("Int64")
    else:
        summary["gender_generated_label"] = "Unknown"
        summary["gender_generated_code"] = 0

    religions = religion_cfg.get("labels", _default_religions())
    counts = religion_cfg.get("counts", _default_counts())
    total_count = sum(counts)
    probs = [c / total_count for c in counts] if total_count > 0 else [1.0 / len(religions)] * len(religions)
    summary["EHR_RELIGION_LABEL"] = np.random.choice(religions, size=len(summary), p=probs)

    religion_mapping = religion_cfg.get("label_to_code", _default_religion_label_to_code())
    summary = _assign_religion_code(summary, religion_mapping)

    pat_id_system = garde_cfg.get("ehr_pat_id_code_system", "http://epic.com/uhealth/clarity/patient.pat_id")
    sex_system = garde_cfg.get("ehr_sex_code_system", "http://epic.com/uhealth/clarity/zc_sex")
    religion_system = garde_cfg.get("ehr_religion_code_system", "http://epic.com/uhealth/clarity/zc_religion")

    w = summary[
        [
            subject_col,
            "anchor_age_generated_dob",
            "gender_generated_label",
            "gender_generated_code",
            "EHR_RELIGION_LABEL",
            "EHR_RELIGION_CODE",
        ]
    ].copy()
    w = w.rename(
        columns={
            subject_col: "EHR_PAT_ID",
            "anchor_age_generated_dob": "BIRTH_DATE",
            "gender_generated_code": "EHR_SEX_CODE",
            "gender_generated_label": "EHR_SEX_LABEL",
        }
    )
    w["EHR_PAT_ID_CODE_SYSTEM"] = pat_id_system
    w["EHR_SEX_CODE_SYSTEM"] = sex_system
    w["EHR_RELIGION_CODE_SYSTEM"] = religion_system
    w["PREV_MET_CRITERIA_LIST"] = ""

    w["BIRTH_DATE"] = w["BIRTH_DATE"].astype(str).str[:10]

    out_cols = [
        "EHR_PAT_ID_CODE_SYSTEM",
        "EHR_PAT_ID",
        "BIRTH_DATE",
        "EHR_SEX_CODE_SYSTEM",
        "EHR_SEX_CODE",
        "EHR_SEX_LABEL",
        "EHR_RELIGION_CODE_SYSTEM",
        "EHR_RELIGION_CODE",
        "EHR_RELIGION_LABEL",
        "PREV_MET_CRITERIA_LIST",
    ]
    w = w[out_cols]
    w.to_csv(output_garde_demographics_csv, index=False)

    return {
        "output_garde_demographics_csv": str(output_garde_demographics_csv),
        "qc": {
            "demographics_rows": int(len(w)),
            "demographics_subjects": int(w["EHR_PAT_ID"].nunique()),
        },
    }


def _default_religions() -> list[str]:
    return [
        "No Spiritual Preference",
        "The Church of Jesus Christ of Latter Day Saints",
        "Did not Ask",
        "Catholic",
        "Christian",
        "Agnostic",
        "No Spiritual Needs",
        "Atheist",
        "Spiritual, not Religious",
        "Non-Denominational Christian",
        "Jehovah's Witness",
        "Inactive LDS",
        "Muslim",
        "Buddhist",
        "Episcopalian",
        "Not on List",
        "Jewish",
        "Baptist",
        "Declined to Answer",
        "Pagan",
        "Presbyterian",
        "Lutheran",
        "Not Verified",
        "Islamic",
        "Protestant",
        "Hindu",
        "Greek Orthodox",
        "Nature",
        "Christian Scientist",
        "Wiccan",
        "New Thought",
        "Shamanism",
        "Taoist",
        "Humanist",
        "Evangelical",
        "Do Not Visit",
        "Methodist",
        "Unitarian",
        "Deist",
        "Did not Indicate",
        "Unable to Answer",
    ]


def _default_counts() -> list[int]:
    return [
        171, 140, 87, 61, 48, 28, 23, 13, 12, 9,
        6, 5, 5, 5, 4, 4, 4, 3, 3, 3,
        3, 3, 3, 2, 2, 2, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    ]


def _default_religion_label_to_code() -> dict[str, float]:
    religion_mapping = {
        51.0: "No Spiritual Preference",
        16.0: "The Church of Jesus Christ of Latter Day Saints",
        63.0: "Did not Ask",
        3.0: "Catholic",
        9.0: "Christian",
        31.0: "Agnostic",
        29.0: "No Spiritual Needs",
        8.0: "Atheist",
        52.0: "Spiritual, not Religious",
        19.0: "Non-Denominational Christian",
        15.0: "Jehovah's Witness",
        57.0: "Inactive LDS",
        18.0: "Muslim",
        6.0: "Buddhist",
        11.0: "Episcopalian",
        56.0: "Not on List",
        2.0: "Jewish",
        4.0: "Baptist",
        50.0: "Declined to Answer",
        40.0: "Pagan",
        22.0: "Presbyterian",
        1.0: "Lutheran",
        30.0: "Not Verified",
        14.0: "Islamic",
        23.0: "Protestant",
        13.0: "Hindu",
        12.0: "Greek Orthodox",
        85.0: "Nature",
        5.0: "Christian Scientist",
        49.0: "Wiccan",
        39.0: "New Thought",
        43.0: "Shamanism",
        75.0: "Taoist",
        36.0: "Humanist",
        55.0: "Evangelical",
        64.0: "Do Not Visit",
        17.0: "Methodist",
        28.0: "Unitarian",
        67.0: "Deist",
        58.0: "Did not Indicate",
        46.0: "Unable to Answer",
    }
    return {label: code for code, label in religion_mapping.items()}
