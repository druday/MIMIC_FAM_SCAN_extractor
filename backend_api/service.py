"""Service layer for stage-by-stage pipeline orchestration."""

from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mimic_repro.config import load_config
from mimic_repro.deviation_report import generate_deviation_report
from mimic_repro.io_utils import compute_sha256, count_csv_rows, ensure_dir, write_json
from mimic_repro.stages.build_validated_cohort import run_build_validated_cohort
from mimic_repro.stages.consolidate_family_history import run_consolidate_family_history
from mimic_repro.stages.export_subset import run_export_subset
from mimic_repro.stages.extract_family_history_notes import run_extract_family_history_notes
from mimic_repro.stages.garde_demographics import run_garde_demographics
from mimic_repro.stages.garde_family_history import run_garde_family_history
from mimic_repro.stages.llm_imputation import run_llm_imputation
from mimic_repro.stages.merge_structured_mimic import run_merge_structured_mimic

from backend_api.models import CreateProfileRequest, CreateRunRequest, StageName


class PipelineService:
    """Manage run contexts, stage execution, and API-facing artifacts."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.artifacts_root = project_root / "artifacts" / "pre_llm"
        self.profiles_path = project_root / "config" / "cancer_profiles.json"
        ensure_dir(self.artifacts_root)
        ensure_dir(self.profiles_path.parent)

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _resolve_path(self, configured: str) -> Path:
        path = Path(configured)
        return path if path.is_absolute() else (self.project_root / path).resolve()

    def _run_dir(self, run_id: str) -> Path:
        return self.artifacts_root / run_id

    def _status_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "run_status.json"

    def _qc_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "qc_summary.json"

    def _manifest_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "run_manifest.json"

    def _deviation_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "deviation_report.json"

    def _load_status(self, run_id: str) -> dict[str, Any]:
        status_path = self._status_path(run_id)
        if not status_path.exists():
            raise FileNotFoundError(f"Run {run_id} does not exist.")
        return json.loads(status_path.read_text(encoding="utf-8"))

    def _save_status(self, run_id: str, payload: dict[str, Any]) -> None:
        write_json(self._status_path(run_id), payload)

    def _load_qc(self, run_id: str) -> dict[str, Any]:
        qc_path = self._qc_path(run_id)
        if not qc_path.exists():
            return {}
        return json.loads(qc_path.read_text(encoding="utf-8"))

    def _save_qc(self, run_id: str, qc: dict[str, Any]) -> None:
        write_json(self._qc_path(run_id), qc)

    def _load_profiles(self) -> list[dict[str, Any]]:
        if not self.profiles_path.exists():
            return []
        return json.loads(self.profiles_path.read_text(encoding="utf-8"))

    def _save_profiles(self, profiles: list[dict[str, Any]]) -> None:
        write_json(self.profiles_path, profiles)

    def create_profile(self, request: CreateProfileRequest) -> dict[str, Any]:
        profiles = self._load_profiles()
        filtered = [p for p in profiles if p["profile_name"] != request.profile_name]
        filtered.append(request.model_dump())
        self._save_profiles(filtered)
        return request.model_dump()

    def list_profiles(self) -> list[dict[str, Any]]:
        return self._load_profiles()

    def _apply_profile(self, config: dict[str, Any], profile_name: str) -> dict[str, Any]:
        profiles = self._load_profiles()
        profile = next((p for p in profiles if p["profile_name"] == profile_name), None)
        if profile is None:
            raise ValueError(f"Profile {profile_name} not found.")

        out = json.loads(json.dumps(config))
        out["keywords"] = profile["keyword_groups"]
        out["structured_data"]["icd_prefixes"] = profile["icd_prefixes"]
        if profile.get("extract_regex"):
            out["family_history"]["extract_regex"] = profile["extract_regex"]
        if profile.get("trim_after_headers"):
            out["family_history"]["trim_after_headers"] = profile["trim_after_headers"]
        return out

    def _apply_config_overrides(
        self, config: dict[str, Any], overrides: dict[str, Any] | None
    ) -> dict[str, Any]:
        if not overrides:
            return config
        out = json.loads(json.dumps(config))

        family = overrides.get("family_history", {})
        if isinstance(family, dict):
            if "extract_regex" in family and family["extract_regex"]:
                out["family_history"]["extract_regex"] = str(family["extract_regex"])
            if "trim_after_headers" in family and isinstance(family["trim_after_headers"], list):
                out["family_history"]["trim_after_headers"] = [
                    str(x).strip() for x in family["trim_after_headers"] if str(x).strip()
                ]

        keywords = overrides.get("keywords", {})
        if isinstance(keywords, dict):
            normalized_keywords: dict[str, list[str]] = {}
            for group, terms in keywords.items():
                if isinstance(terms, list):
                    normalized_keywords[str(group)] = [
                        str(term).strip() for term in terms if str(term).strip()
                    ]
            if normalized_keywords:
                out["keywords"] = normalized_keywords

        structured = overrides.get("structured_data", {})
        if isinstance(structured, dict):
            if "icd_prefixes" in structured and isinstance(structured["icd_prefixes"], list):
                out["structured_data"]["icd_prefixes"] = [
                    str(x).strip() for x in structured["icd_prefixes"] if str(x).strip()
                ]

        cohort = overrides.get("cohort", {})
        if isinstance(cohort, dict):
            refiners = cohort.get("refiners", {})
            if isinstance(refiners, dict):
                out.setdefault("cohort", {})
                out["cohort"].setdefault("refiners", {})
                if "enabled" in refiners:
                    out["cohort"]["refiners"]["enabled"] = bool(refiners["enabled"])
                if "genders" in refiners and isinstance(refiners["genders"], list):
                    out["cohort"]["refiners"]["genders"] = [
                        str(x).strip() for x in refiners["genders"] if str(x).strip()
                    ]
                if "age_min" in refiners:
                    out["cohort"]["refiners"]["age_min"] = refiners["age_min"]
                if "age_max" in refiners:
                    out["cohort"]["refiners"]["age_max"] = refiners["age_max"]
                if "cancer_types" in refiners and isinstance(refiners["cancer_types"], list):
                    out["cohort"]["refiners"]["cancer_types"] = [
                        str(x).strip() for x in refiners["cancer_types"] if str(x).strip()
                    ]
                if "note_length_min" in refiners:
                    out["cohort"]["refiners"]["note_length_min"] = refiners["note_length_min"]
                if "note_length_max" in refiners:
                    out["cohort"]["refiners"]["note_length_max"] = refiners["note_length_max"]
                if "notes_per_patient_min" in refiners:
                    out["cohort"]["refiners"]["notes_per_patient_min"] = refiners[
                        "notes_per_patient_min"
                    ]
                if "notes_per_patient_max" in refiners:
                    out["cohort"]["refiners"]["notes_per_patient_max"] = refiners[
                        "notes_per_patient_max"
                    ]
        llm = overrides.get("llm", {})
        if isinstance(llm, dict):
            out.setdefault("llm", {})
            if "provider" in llm:
                out["llm"]["provider"] = str(llm["provider"]).lower().strip() or "openai"
            if "model" in llm and llm["model"]:
                out["llm"]["model"] = str(llm["model"]).strip()
            if "temperature" in llm and llm["temperature"] is not None:
                out["llm"]["temperature"] = float(llm["temperature"])
            if "max_tokens" in llm and llm["max_tokens"] is not None:
                out["llm"]["max_tokens"] = int(llm["max_tokens"])
        garde_export = overrides.get("garde_export", {})
        if isinstance(garde_export, dict) and "enabled" in garde_export:
            out.setdefault("garde_export", {})
            out["garde_export"]["enabled"] = bool(garde_export["enabled"])
        export_subset = overrides.get("export_subset", {})
        if isinstance(export_subset, dict):
            out.setdefault("export_subset", {})
            if "enabled" in export_subset:
                out["export_subset"]["enabled"] = bool(export_subset["enabled"])
            if "max_patients" in export_subset and export_subset["max_patients"] is not None:
                out["export_subset"]["max_patients"] = int(export_subset["max_patients"])
            for key in ("age_min", "age_max", "records_per_patient_min", "records_per_patient_max"):
                if key in export_subset:
                    val = export_subset[key]
                    out["export_subset"][key] = None if val is None else int(val)
            if "random_seed" in export_subset and export_subset["random_seed"] is not None:
                out["export_subset"]["random_seed"] = int(export_subset["random_seed"])
        return out

    def create_run(self, request: CreateRunRequest) -> dict[str, Any]:
        run_dir = self._run_dir(request.run_id)
        if run_dir.exists():
            raise FileExistsError(f"Run {request.run_id} already exists.")
        ensure_dir(run_dir)

        config_path = self._resolve_path(request.config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file does not exist: {config_path}")
        config = load_config(config_path)
        if request.profile_name:
            config = self._apply_profile(config, request.profile_name)
        config = self._apply_config_overrides(config, request.config_overrides)

        config_snapshot = run_dir / "config_snapshot.json"
        write_json(config_snapshot, config)

        status = {
            "run_id": request.run_id,
            "created_at": self._now(),
            "updated_at": self._now(),
            "profile_name": request.profile_name,
            "config_path": str(config_path),
            "config_snapshot_path": str(config_snapshot),
            "stages": {
                "stage1": {"status": "pending", "started_at": None, "ended_at": None, "error": None},
                "stage2": {"status": "pending", "started_at": None, "ended_at": None, "error": None},
                "stage3": {"status": "pending", "started_at": None, "ended_at": None, "error": None},
                "stage4": {"status": "pending", "started_at": None, "ended_at": None, "error": None},
            },
            "outputs": {
                "stage1_notes": str(run_dir / "family_history_notes_extracted.csv"),
                "stage1_keyword_positive": str(run_dir / "family_history_keyword_positive.csv"),
                "stage2_keyword_cohort": str(run_dir / "keyword_positive_cohort.csv"),
                "stage3_merged": str(run_dir / "merged_df.csv"),
                "stage4_garde_demographics": str(run_dir / "GARDE_demographics.csv"),
                "stage4_garde_family_history": str(run_dir / "GARDE_family_history.csv"),
                "qc_summary": str(self._qc_path(request.run_id)),
                "deviation_report": str(self._deviation_path(request.run_id)),
                "run_manifest": str(self._manifest_path(request.run_id)),
            },
        }
        self._save_status(request.run_id, status)
        return status

    @staticmethod
    def _export_subset_enabled(config: dict[str, Any]) -> bool:
        """Subset before Stage 4 when enabled; default True so cohort is capped unless explicitly off."""
        block = config.get("export_subset")
        if not isinstance(block, dict):
            return True
        return bool(block.get("enabled", True))

    def _assert_stage_preconditions(self, status: dict[str, Any], stage: StageName) -> None:
        if stage == "stage1":
            return
        if stage == "stage2" and status["stages"]["stage1"]["status"] != "success":
            raise ValueError("stage1 must complete successfully before stage2.")
        if stage == "stage3":
            if status["stages"]["stage1"]["status"] != "success":
                raise ValueError("stage1 must complete successfully before stage3.")
            if status["stages"]["stage2"]["status"] != "success":
                raise ValueError("stage2 must complete successfully before stage3.")
        if stage == "stage4":
            if status["stages"]["stage1"]["status"] != "success":
                raise ValueError("stage1 must complete successfully before stage4.")
            if status["stages"]["stage2"]["status"] != "success":
                raise ValueError("stage2 must complete successfully before stage4.")
            if status["stages"]["stage3"]["status"] != "success":
                raise ValueError("stage3 must complete successfully before stage4.")

    def _build_manifest(self, run_id: str, status: dict[str, Any], config_path: Path) -> dict[str, Any]:
        snapshot_path = Path(status["config_snapshot_path"])
        config_snapshot = load_config(snapshot_path)
        paths = config_snapshot["paths"]
        run_dir = self._run_dir(run_id)

        def file_entry(path: Path) -> dict[str, Any]:
            return {
                "path": str(path),
                "exists": path.exists(),
                "sha256": compute_sha256(path) if path.exists() else None,
                "rows": count_csv_rows(path) if path.exists() and path.suffix.lower() == ".csv" else None,
            }

        inputs = {
            "discharge_csv": file_entry(self._resolve_path(paths["discharge_csv"])),
            "admissions_csv": file_entry(self._resolve_path(paths["admissions_csv"])),
            "diagnoses_icd_csv": file_entry(self._resolve_path(paths["diagnoses_icd_csv"])),
            "patients_csv": file_entry(self._resolve_path(paths["patients_csv"])),
        }
        garde_enabled = config_snapshot.get("garde_export", {}).get("enabled", False)
        outputs = {
            "family_history_notes_extracted_csv": file_entry(
                run_dir / "family_history_notes_extracted.csv"
            ),
            "family_history_keyword_positive_csv": file_entry(
                run_dir / "family_history_keyword_positive.csv"
            ),
            "keyword_positive_cohort_csv": file_entry(run_dir / "keyword_positive_cohort.csv"),
            "merged_df_csv": file_entry(run_dir / "merged_df.csv"),
            "GARDE_demographics_csv": file_entry(run_dir / "GARDE_demographics.csv") if garde_enabled else {"path": str(run_dir / "GARDE_demographics.csv"), "exists": False, "sha256": None, "rows": None},
            "GARDE_family_history_csv": file_entry(run_dir / "GARDE_family_history.csv") if garde_enabled else {"path": str(run_dir / "GARDE_family_history.csv"), "exists": False, "sha256": None, "rows": None},
            "qc_summary_json": file_entry(self._qc_path(run_id)),
            "deviation_report_json": file_entry(self._deviation_path(run_id)),
        }
        return {
            "run_id": run_id,
            "timestamp_utc": self._now(),
            "config_path": str(config_path),
            "config_snapshot_path": str(snapshot_path),
            "config_snapshot_sha256": compute_sha256(snapshot_path),
            "inputs": inputs,
            "outputs": outputs,
        }

    def run_stage(
        self, run_id: str, stage: StageName, config_overrides: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        status = self._load_status(run_id)
        self._assert_stage_preconditions(status, stage)

        status["stages"][stage]["status"] = "running"
        status["stages"][stage]["started_at"] = self._now()
        status["stages"][stage]["error"] = None
        status["updated_at"] = self._now()
        self._save_status(run_id, status)

        run_dir = self._run_dir(run_id)
        config_snapshot_path = Path(status["config_snapshot_path"])
        config = load_config(config_snapshot_path)
        if config_overrides:
            config = self._apply_config_overrides(config, config_overrides)

        try:
            if stage == "stage1":
                response = run_extract_family_history_notes(
                    discharge_csv=self._resolve_path(config["paths"]["discharge_csv"]),
                    output_notes_csv=run_dir / "family_history_notes_extracted.csv",
                    output_keyword_positive_csv=run_dir / "family_history_keyword_positive.csv",
                    config=config,
                )
                qc_key = "stage1_extract_family_history_notes"
            elif stage == "stage2":
                response = run_build_validated_cohort(
                    keyword_positive_notes_csv=run_dir / "family_history_keyword_positive.csv",
                    patients_csv=self._resolve_path(config["paths"]["patients_csv"]),
                    output_keyword_positive_cohort_csv=run_dir / "keyword_positive_cohort.csv",
                    config=config,
                )
                qc_key = "stage2_build_validated_cohort"
            elif stage == "stage3":
                response = run_merge_structured_mimic(
                    validated_notes_csv=run_dir / "keyword_positive_cohort.csv",
                    admissions_csv=self._resolve_path(config["paths"]["admissions_csv"]),
                    diagnoses_icd_csv=self._resolve_path(config["paths"]["diagnoses_icd_csv"]),
                    patients_csv=self._resolve_path(config["paths"]["patients_csv"]),
                    output_merged_csv=run_dir / "merged_df.csv",
                    config=config,
                )
                qc_key = "stage3_merge_structured_mimic"
            else:
                garde_enabled = config.get("garde_export", {}).get("enabled", False)
                if not garde_enabled:
                    raise ValueError("Stage 4 requires garde_export.enabled=true in config.")
                subset_enabled = self._export_subset_enabled(config)
                if subset_enabled:
                    cohort_subset_csv = run_dir / "keyword_positive_cohort_subset.csv"
                    merged_subset_csv = run_dir / "merged_df_subset.csv"
                    subset_qc = run_export_subset(
                        cohort_csv=run_dir / "keyword_positive_cohort.csv",
                        merged_df_csv=run_dir / "merged_df.csv",
                        output_cohort_subset_csv=cohort_subset_csv,
                        output_merged_subset_csv=merged_subset_csv,
                        config=config,
                    )
                    subset_qc["subset_applied"] = True
                    stage4_cohort_csv = cohort_subset_csv
                    stage4_merged_csv = merged_subset_csv
                else:
                    stage4_cohort_csv = run_dir / "keyword_positive_cohort.csv"
                    stage4_merged_csv = run_dir / "merged_df.csv"
                    subset_qc = {
                        "subset_applied": False,
                        "reason": (
                            "export_subset.enabled is false in effective config; "
                            "GARDE used full cohort CSVs."
                        ),
                        "export_subset": config.get("export_subset"),
                    }

                stage4a = run_garde_demographics(
                    merged_df_csv=stage4_merged_csv,
                    cohort_csv=stage4_cohort_csv,
                    output_garde_demographics_csv=run_dir / "GARDE_demographics.csv",
                    config=config,
                )
                consolidated_df, stage4b_qc = run_consolidate_family_history(
                    cohort_csv=stage4_cohort_csv,
                    merged_df_csv=stage4_merged_csv,
                    config=config,
                )
                imputed_df, stage4c_qc = run_llm_imputation(consolidated_df, config)
                stage4d = run_garde_family_history(
                    imputed_df=imputed_df,
                    output_garde_family_history_csv=run_dir / "GARDE_family_history.csv",
                    config=config,
                    merged_df_csv=stage4_merged_csv,
                )
                stage4_qc = {
                    "stage4a": stage4a["qc"],
                    "stage4b": stage4b_qc,
                    "stage4c": stage4c_qc,
                    "stage4d": stage4d["qc"],
                    "stage4_subset": subset_qc,
                }
                response = {"qc": stage4_qc}
                qc_key = "stage4_garde_export"

            qc = self._load_qc(run_id)
            qc[qc_key] = response["qc"]
            self._save_qc(run_id, qc)

            if stage == "stage3":
                generate_deviation_report(project_root=self.project_root, run_dir=run_dir)

            manifest = self._build_manifest(
                run_id=run_id,
                status=status,
                config_path=Path(status["config_path"]),
            )
            write_json(self._manifest_path(run_id), manifest)

            status = self._load_status(run_id)
            status["stages"][stage]["status"] = "success"
            status["stages"][stage]["ended_at"] = self._now()
            status["updated_at"] = self._now()
            self._save_status(run_id, status)
            return {"run_id": run_id, "stage": stage, "status": "success", "qc": response["qc"]}

        except Exception as exc:
            status = self._load_status(run_id)
            status["stages"][stage]["status"] = "failed"
            status["stages"][stage]["ended_at"] = self._now()
            status["stages"][stage]["error"] = str(exc)
            status["updated_at"] = self._now()
            self._save_status(run_id, status)
            return {
                "run_id": run_id,
                "stage": stage,
                "status": "failed",
                "error": str(exc),
                "qc": None,
            }

    def run_all_stages(
        self, run_id: str, stage4_config_overrides: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run stages 1-4 sequentially, skipping completed, stopping on first failure."""
        all_stages: list[StageName] = ["stage1", "stage2", "stage3", "stage4"]
        last_result: dict[str, Any] = {}
        for stage in all_stages:
            status = self._load_status(run_id)
            if status["stages"][stage]["status"] == "success":
                continue
            overrides = stage4_config_overrides if stage == "stage4" else None
            last_result = self.run_stage(run_id, stage, config_overrides=overrides)
            if last_result.get("status") == "failed":
                return last_result
        return last_result or {"run_id": run_id, "stage": "stage4", "status": "success", "qc": self._load_qc(run_id)}

    def get_status(self, run_id: str) -> dict[str, Any]:
        return self._load_status(run_id)

    def read_artifact(self, run_id: str, artifact_name: str) -> dict[str, Any]:
        status = self._load_status(run_id)
        artifact_paths = {
            "qc": self._qc_path(run_id),
            "manifest": self._manifest_path(run_id),
            "deviation": self._deviation_path(run_id),
            "config": Path(status["config_snapshot_path"]),
        }
        if artifact_name not in artifact_paths:
            raise ValueError(f"Unsupported artifact name: {artifact_name}")
        path = artifact_paths[artifact_name]
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {artifact_name}")
        return json.loads(path.read_text(encoding="utf-8"))

