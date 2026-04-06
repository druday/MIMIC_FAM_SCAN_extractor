"""Stage 4d: GARDE / FAM-SCAN family history CSV export (16-column Epic-shaped schema)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pandas as pd

# Column order matches GARDE demo ut-DE-ID-pat-fhx (final consumer).
GARDE_FAMILY_HISTORY_COLUMNS: tuple[str, ...] = (
    "EHR_FAMILY_HX_ID_CODE_SYSTEM",
    "EHR_FAMILY_HX_ID",
    "EHR_PAT_ID_CODE_SYSTEM",
    "EHR_PAT_ID",
    "EHR_ENC_ID_CODE_SYSTEM",
    "EHR_ENC_ID",
    "EHR_REC_ID",
    "EHR_REC_DT",
    "EHR_COND_CODE_SYSTEM",
    "EHR_COND_CODE",
    "EHR_COND_LABEL",
    "EHR_RELATION_CODE_SYSTEM",
    "EHR_RELATION_CODE",
    "EHR_RELATION_LABEL",
    "EHR_COND_ONSET_AGE",
    "EHR_COMMENTS",
)

_NS_MIMIC_FHX = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace for uuid5


def format_icd_prefix_for_comments(merged_icd_codes: Any) -> str:
    """
    Build optional `{icd1, icd2} ` prefix for EHR_COMMENTS.
    Never emits literal 'nan' or braces when no real ICDs are present.
    """
    if merged_icd_codes is None:
        return ""
    try:
        if pd.isna(merged_icd_codes):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(merged_icd_codes).strip()
    if not s or s.lower() == "nan":
        return ""
    return "{" + s + "} "


def _merge_encounter_fields(
    df: pd.DataFrame,
    subject_col: str,
    merged_df_csv: Path | None,
) -> pd.DataFrame:
    """Attach first hadm_id / admittime per subject from merged MIMIC table (patient-level export)."""
    if merged_df_csv is None or not merged_df_csv.is_file():
        return df
    try:
        merged = pd.read_csv(merged_df_csv)
    except Exception:
        return df
    if subject_col not in merged.columns:
        return df
    cols = [subject_col]
    for c in ("hadm_id", "admittime"):
        if c in merged.columns:
            cols.append(c)
    if len(cols) < 2:
        return df
    sub = merged[cols].drop_duplicates(subset=[subject_col], keep="first")
    return df.merge(sub, on=subject_col, how="left")


def _safe_str_id(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    return str(val).strip()


def _format_rec_dt(raw: Any) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    try:
        if pd.isna(raw):
            return ""
    except (TypeError, ValueError):
        pass
    ts = pd.to_datetime(raw, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y-%m-%d")


def run_garde_family_history(
    imputed_df: pd.DataFrame,
    output_garde_family_history_csv: Path,
    config: dict[str, Any],
    merged_df_csv: Path | None = None,
) -> dict[str, Any]:
    """
    Export 16-column family history CSV aligned with GARDE demo / FAM-SCAN (post-alignment).

    One row per patient: consolidated/imputed narrative + optional ICD prefix in EHR_COMMENTS;
    EHR_REC_ID is always 1; stable EHR_FAMILY_HX_ID per patient.
    """
    fh_cfg = config["family_history"]
    garde_cfg = config.get("garde", {})
    garde_fh_cfg = garde_cfg.get("family_history", {})
    subject_col = fh_cfg["subject_id_column"]
    max_length = int(garde_fh_cfg.get("max_length", 1500))

    ph = garde_fh_cfg.get("placeholders") or {}
    cond_code = str(ph.get("ehr_cond_code", "29"))
    cond_label = str(ph.get("ehr_cond_label", "OTHER"))
    rel_code = str(ph.get("ehr_relation_code", "14"))
    rel_label = str(ph.get("ehr_relation_label", "OTHER"))

    sys_urls = garde_fh_cfg.get("code_systems") or {}
    family_hx_id_cs = sys_urls.get(
        "ehr_family_hx_id",
        "http://epic.com/uhealth/clarity/family_hx/pat_id__pat_enc_csn_id__line",
    )
    pat_id_cs = garde_cfg.get("ehr_pat_id_code_system", "http://epic.com/uhealth/clarity/patient.pat_id")
    enc_id_cs = sys_urls.get(
        "ehr_enc_id",
        "http://epic.com/uhealth/clarity/pat_enc.pat_enc_csn_id",
    )
    cond_cs = sys_urls.get("ehr_cond", "http://epic.com/uhealth/clarity/zc_medical_hx")
    relation_cs = sys_urls.get("ehr_relation", "http://epic.com/uhealth/clarity/zc_relation")

    if merged_df_csv is None:
        paths = config.get("paths") or {}
        cand = paths.get("merged_df_csv_for_garde")
        if cand:
            merged_df_csv = Path(cand)

    df = imputed_df.copy()
    df = _merge_encounter_fields(df, subject_col, merged_df_csv)

    if "imputed_family_history" in df.columns:
        text_col = "imputed_family_history"
    else:
        text_col = "merged_family_history"

    rows: list[dict[str, Any]] = []
    dropped = 0

    for _, row in df.iterrows():
        sid = row.get(subject_col)
        pat_id = _safe_str_id(sid)
        narrative = _safe_str_id(row.get(text_col, ""))
        icd_prefix = format_icd_prefix_for_comments(row.get("merged_icd_codes"))
        comments = (icd_prefix + narrative).strip()

        if len(comments) > max_length:
            dropped += 1
            continue

        hadm = row.get("hadm_id") if "hadm_id" in df.columns else None
        enc_id = _safe_str_id(hadm)

        adm = row.get("admittime") if "admittime" in df.columns else None
        rec_dt = _format_rec_dt(adm)

        rec_id = 1
        fhx_uuid = str(uuid.uuid5(_NS_MIMIC_FHX, f"{pat_id}|{rec_id}"))

        rows.append(
            {
                "EHR_FAMILY_HX_ID_CODE_SYSTEM": family_hx_id_cs,
                "EHR_FAMILY_HX_ID": fhx_uuid,
                "EHR_PAT_ID_CODE_SYSTEM": pat_id_cs,
                "EHR_PAT_ID": pat_id,
                "EHR_ENC_ID_CODE_SYSTEM": enc_id_cs,
                "EHR_ENC_ID": enc_id,
                "EHR_REC_ID": rec_id,
                "EHR_REC_DT": rec_dt,
                "EHR_COND_CODE_SYSTEM": cond_cs,
                "EHR_COND_CODE": cond_code,
                "EHR_COND_LABEL": cond_label,
                "EHR_RELATION_CODE_SYSTEM": relation_cs,
                "EHR_RELATION_CODE": rel_code,
                "EHR_RELATION_LABEL": rel_label,
                "EHR_COND_ONSET_AGE": "",
                "EHR_COMMENTS": comments,
            }
        )

    out = pd.DataFrame(rows, columns=list(GARDE_FAMILY_HISTORY_COLUMNS))
    output_garde_family_history_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_garde_family_history_csv, index=False)

    n_subj = int(out["EHR_PAT_ID"].nunique()) if len(out) else 0
    n_rows = int(len(out))

    return {
        "output_garde_family_history_csv": str(output_garde_family_history_csv),
        "qc": {
            "family_history_rows": n_rows,
            "family_history_subjects": n_subj,
            "rows_dropped_over_length": dropped,
            "max_length_threshold": max_length,
            "schema_columns": len(GARDE_FAMILY_HISTORY_COLUMNS),
            "column_order": "garde_demo_ut_DE_ID_pat_fhx",
        },
    }
