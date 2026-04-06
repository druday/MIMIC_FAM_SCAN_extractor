"""Data quality checks and QC summary helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd


def require_columns(df: pd.DataFrame, required: list[str], frame_name: str) -> None:
    """Raise an error if required columns are missing."""
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"{frame_name} is missing required columns: {missing}")


def require_any_column(df: pd.DataFrame, candidates: list[str], frame_name: str) -> str:
    """Return the first matching column from candidates or raise."""
    for column in candidates:
        if column in df.columns:
            return column
    raise ValueError(f"{frame_name} must contain at least one of: {candidates}")


def summarize_frame(
    df: pd.DataFrame,
    frame_name: str,
    subject_id_col: str | None = None,
    duplicate_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Create a compact QC summary for a dataframe."""
    summary: dict[str, Any] = {
        "frame_name": frame_name,
        "rows": int(len(df)),
        "columns": sorted([str(c) for c in df.columns]),
    }
    if subject_id_col and subject_id_col in df.columns:
        summary["unique_subjects"] = int(df[subject_id_col].nunique(dropna=True))
        summary["null_subject_id_rows"] = int(df[subject_id_col].isna().sum())
    if duplicate_keys:
        existing_keys = [k for k in duplicate_keys if k in df.columns]
        if existing_keys:
            summary["duplicate_rows_on_keys"] = int(df.duplicated(subset=existing_keys).sum())
    # Report null percentage for key columns only to keep QC concise.
    summary["null_pct"] = {
        str(col): round(float(df[col].isna().mean() * 100), 2)
        for col in df.columns
        if col in {subject_id_col, "note_id", "family_history", "icd_code"}
    }
    return summary

