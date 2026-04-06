"""Top-level runner for the reproducible pre-LLM MIMIC pipeline."""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from mimic_repro.config import load_config
from mimic_repro.deviation_report import generate_deviation_report
from mimic_repro.io_utils import compute_sha256, count_csv_rows, ensure_dir, utc_timestamp, write_json
from mimic_repro.stages.build_validated_cohort import run_build_validated_cohort
from mimic_repro.stages.consolidate_family_history import run_consolidate_family_history
from mimic_repro.stages.export_subset import run_export_subset
from mimic_repro.stages.extract_family_history_notes import run_extract_family_history_notes
from mimic_repro.stages.garde_demographics import run_garde_demographics
from mimic_repro.stages.garde_family_history import run_garde_family_history
from mimic_repro.stages.llm_imputation import run_llm_imputation
from mimic_repro.stages.merge_structured_mimic import run_merge_structured_mimic


def _resolve_path(base_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def _git_commit_hash(repo_dir: Path) -> str | None:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, stderr=subprocess.DEVNULL, text=True
        )
        return output.strip()
    except Exception:
        return None


def _file_manifest_entry(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": compute_sha256(path) if path.exists() else None,
        "rows": count_csv_rows(path) if path.exists() and path.suffix.lower() == ".csv" else None,
    }


def run_pipeline(config_path: Path, run_name: str | None = None) -> Path:
    config = load_config(config_path)
    project_root = config_path.parent.parent.resolve()

    paths = config["paths"]
    artifacts_root = _resolve_path(project_root, paths["artifacts_root"])
    run_id = run_name or f"run_{utc_timestamp()}"
    run_dir = artifacts_root / run_id
    ensure_dir(run_dir)

    discharge_csv = _resolve_path(project_root, paths["discharge_csv"])
    admissions_csv = _resolve_path(project_root, paths["admissions_csv"])
    diagnoses_icd_csv = _resolve_path(project_root, paths["diagnoses_icd_csv"])
    patients_csv = _resolve_path(project_root, paths["patients_csv"])

    extracted_notes_csv = run_dir / "family_history_notes_extracted.csv"
    keyword_positive_csv = run_dir / "family_history_keyword_positive.csv"
    keyword_positive_cohort_csv = run_dir / "keyword_positive_cohort.csv"
    merged_df_csv = run_dir / "merged_df.csv"

    stage1 = run_extract_family_history_notes(
        discharge_csv=discharge_csv,
        output_notes_csv=extracted_notes_csv,
        output_keyword_positive_csv=keyword_positive_csv,
        config=config,
    )
    stage2 = run_build_validated_cohort(
        keyword_positive_notes_csv=keyword_positive_csv,
        patients_csv=patients_csv,
        output_keyword_positive_cohort_csv=keyword_positive_cohort_csv,
        config=config,
    )
    stage3 = run_merge_structured_mimic(
        validated_notes_csv=keyword_positive_cohort_csv,
        admissions_csv=admissions_csv,
        diagnoses_icd_csv=diagnoses_icd_csv,
        patients_csv=patients_csv,
        output_merged_csv=merged_df_csv,
        config=config,
    )

    qc_summary = {
        "stage1_extract_family_history_notes": stage1["qc"],
        "stage2_build_validated_cohort": stage2["qc"],
        "stage3_merge_structured_mimic": stage3["qc"],
    }

    garde_demographics_csv = run_dir / "GARDE_demographics.csv"
    garde_family_history_csv = run_dir / "GARDE_family_history.csv"
    garde_enabled = config.get("garde_export", {}).get("enabled", False)

    if garde_enabled:
        subset_block = config.get("export_subset")
        subset_enabled = subset_block.get("enabled", True) if isinstance(subset_block, dict) else True
        if subset_enabled:
            cohort_subset_csv = run_dir / "keyword_positive_cohort_subset.csv"
            merged_subset_csv = run_dir / "merged_df_subset.csv"
            subset_qc = run_export_subset(
                cohort_csv=keyword_positive_cohort_csv,
                merged_df_csv=merged_df_csv,
                output_cohort_subset_csv=cohort_subset_csv,
                output_merged_subset_csv=merged_subset_csv,
                config=config,
            )
            qc_summary["stage4_subset"] = subset_qc
            stage4_cohort_csv = cohort_subset_csv
            stage4_merged_csv = merged_subset_csv
        else:
            stage4_cohort_csv = keyword_positive_cohort_csv
            stage4_merged_csv = merged_df_csv

        stage4a = run_garde_demographics(
            merged_df_csv=stage4_merged_csv,
            cohort_csv=stage4_cohort_csv,
            output_garde_demographics_csv=garde_demographics_csv,
            config=config,
        )
        qc_summary["stage4a_garde_demographics"] = stage4a["qc"]

        consolidated_df, stage4b_qc = run_consolidate_family_history(
            cohort_csv=stage4_cohort_csv,
            merged_df_csv=stage4_merged_csv,
            config=config,
        )
        qc_summary["stage4b_consolidate_family_history"] = stage4b_qc

        imputed_df, stage4c_qc = run_llm_imputation(consolidated_df, config)
        qc_summary["stage4c_llm_imputation"] = stage4c_qc

        stage4d = run_garde_family_history(
            imputed_df=imputed_df,
            output_garde_family_history_csv=garde_family_history_csv,
            config=config,
            merged_df_csv=stage4_merged_csv,
        )
        qc_summary["stage4d_garde_family_history"] = stage4d["qc"]
    write_json(run_dir / "qc_summary.json", qc_summary)
    deviation_report_path = generate_deviation_report(project_root=project_root, run_dir=run_dir)

    manifest = {
        "run_id": run_id,
        "timestamp_utc": utc_timestamp(),
        "system": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "cwd": os.getcwd(),
            "git_commit": _git_commit_hash(project_root),
        },
        "config_path": str(config_path.resolve()),
        "config_sha256": compute_sha256(config_path.resolve()),
        "inputs": {
            "discharge_csv": _file_manifest_entry(discharge_csv),
            "admissions_csv": _file_manifest_entry(admissions_csv),
            "diagnoses_icd_csv": _file_manifest_entry(diagnoses_icd_csv),
            "patients_csv": _file_manifest_entry(patients_csv),
        },
        "outputs": {
            "family_history_notes_extracted_csv": _file_manifest_entry(extracted_notes_csv),
            "family_history_keyword_positive_csv": _file_manifest_entry(keyword_positive_csv),
            "keyword_positive_cohort_csv": _file_manifest_entry(keyword_positive_cohort_csv),
            "merged_df_csv": _file_manifest_entry(merged_df_csv),
            "GARDE_demographics_csv": _file_manifest_entry(garde_demographics_csv) if garde_enabled else {"path": str(garde_demographics_csv), "exists": False, "sha256": None, "rows": None},
            "GARDE_family_history_csv": _file_manifest_entry(garde_family_history_csv) if garde_enabled else {"path": str(garde_family_history_csv), "exists": False, "sha256": None, "rows": None},
            "qc_summary_json": {
                "path": str((run_dir / "qc_summary.json")),
                "sha256": compute_sha256(run_dir / "qc_summary.json"),
            },
            "deviation_report_json": {
                "path": str(deviation_report_path),
                "sha256": compute_sha256(deviation_report_path),
            },
        },
    }
    write_json(run_dir / "run_manifest.json", manifest)
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run reproducible pre-LLM MIMIC pipeline.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/pre_llm_config.json"),
        help="Path to the JSON config file.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Optional run directory name under artifacts root.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_dir = run_pipeline(config_path=args.config.resolve(), run_name=args.run_name)
    print(f"Pipeline completed. Artifacts written to: {run_dir}")


if __name__ == "__main__":
    main()

