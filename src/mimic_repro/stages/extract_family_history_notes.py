"""Stage 1: Extract family history text and keyword-positive notes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from mimic_repro.quality import require_columns, summarize_frame


def _extract_family_history(text: Any, pattern: re.Pattern[str]) -> str | None:
    if not isinstance(text, str):
        return None
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()


def _trim_after_headers(text: str, headers: list[str]) -> str:
    trimmed = text
    for header in headers:
        needle = f"\n{header}"
        if needle in trimmed:
            trimmed = trimmed.split(needle, 1)[0]
    return trimmed.strip()


def _contains_any_keyword(text: str, keywords: list[str]) -> bool:
    lower_text = text.lower()
    return any(keyword.lower() in lower_text for keyword in keywords)


def _keyword_audit(keyword_cfg: dict[str, list[str]]) -> dict[str, Any]:
    normalized = {
        name: [entry.strip().lower() for entry in entries]
        for name, entries in keyword_cfg.items()
    }
    per_category = {}
    for name, terms in normalized.items():
        unique_terms = sorted(set(terms))
        duplicates = sorted({term for term in terms if terms.count(term) > 1})
        per_category[name] = {
            "configured_terms": len(keyword_cfg[name]),
            "unique_terms": len(unique_terms),
            "duplicate_terms": duplicates,
        }
    categories = sorted(normalized.keys())
    overlap = {}
    for idx, left in enumerate(categories):
        for right in categories[idx + 1 :]:
            shared = sorted(set(normalized[left]).intersection(normalized[right]))
            overlap[f"{left}_x_{right}"] = shared
    return {"per_category": per_category, "cross_category_overlap": overlap}


def run_extract_family_history_notes(
    discharge_csv: Path,
    output_notes_csv: Path,
    output_keyword_positive_csv: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Execute extraction and keyword filtering from discharge notes."""
    fh_cfg = config["family_history"]
    keyword_cfg = config["keywords"]
    qc_cfg = config["quality_checks"]

    df = pd.read_csv(discharge_csv)
    require_columns(df, qc_cfg["required_discharge_columns"], "discharge_csv")

    pattern = re.compile(fh_cfg["extract_regex"], re.DOTALL)
    text_col = fh_cfg["text_column"]
    subject_col = fh_cfg["subject_id_column"]

    df = df.copy()
    df["family_history"] = df[text_col].apply(lambda x: _extract_family_history(x, pattern))
    df = df.dropna(subset=["family_history"]).reset_index(drop=True)
    df["family_history"] = df["family_history"].apply(
        lambda x: _trim_after_headers(x, fh_cfg["trim_after_headers"])
    )

    df["breast_cancer_mention"] = df["family_history"].apply(
        lambda x: _contains_any_keyword(x, keyword_cfg["breast"])
    )
    df["ovarian_cancer_mention"] = df["family_history"].apply(
        lambda x: _contains_any_keyword(x, keyword_cfg["ovarian"])
    )
    df["colorectal_cancer_mention"] = df["family_history"].apply(
        lambda x: _contains_any_keyword(x, keyword_cfg["colorectal"])
    )
    df["any_cancer_keyword_mention"] = (
        df["breast_cancer_mention"]
        | df["ovarian_cancer_mention"]
        | df["colorectal_cancer_mention"]
    )

    keyword_positive = df[df["any_cancer_keyword_mention"]].copy().reset_index(drop=True)

    df.to_csv(output_notes_csv, index=False)
    keyword_positive.to_csv(output_keyword_positive_csv, index=False)
    extracted_subjects = int(df[subject_col].nunique(dropna=True))
    keyword_positive_subjects = int(keyword_positive[subject_col].nunique(dropna=True))

    return {
        "input_file": str(discharge_csv),
        "output_notes_csv": str(output_notes_csv),
        "output_keyword_positive_csv": str(output_keyword_positive_csv),
        "qc": {
            "extracted_notes": summarize_frame(
                df, "family_history_notes", subject_id_col=subject_col, duplicate_keys=["note_id"]
            ),
            "keyword_positive_notes": summarize_frame(
                keyword_positive,
                "keyword_positive_notes",
                subject_id_col=subject_col,
                duplicate_keys=["note_id"],
            ),
            "lineage": {
                "extracted_subjects": extracted_subjects,
                "keyword_positive_subjects": keyword_positive_subjects,
                "subjects_dropped_after_keyword_filter": extracted_subjects - keyword_positive_subjects,
            },
            "keyword_audit": _keyword_audit(keyword_cfg),
        },
    }

