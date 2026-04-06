"""Pydantic models for pipeline operator API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


StageName = Literal["stage1", "stage2", "stage3", "stage4"]


class CreateRunRequest(BaseModel):
    run_id: str = Field(..., description="Run identifier used under artifacts/pre_llm")
    config_path: str = Field(
        default="config/pre_llm_config.json",
        description="Path to config file relative to project root or absolute",
    )
    profile_name: str | None = Field(
        default=None,
        description="Optional cancer profile name to override keyword and ICD settings.",
    )
    config_overrides: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional inline config overrides for run snapshot. "
            "Supports keys like family_history.extract_regex, "
            "family_history.trim_after_headers, keywords.*, structured_data.icd_prefixes."
        ),
    )


class CreateProfileRequest(BaseModel):
    profile_name: str
    keyword_groups: dict[str, list[str]]
    icd_prefixes: list[str]
    extract_regex: str | None = None
    trim_after_headers: list[str] | None = None


class RunStageRequest(BaseModel):
    config_overrides: dict[str, Any] | None = Field(
        default=None,
        description="Optional config overrides for this stage run (e.g. export_subset).",
    )


class RunAllRequest(BaseModel):
    config_overrides: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional overrides merged into config when running stage 4 only "
            "(e.g. export_subset from the operator console)."
        ),
    )


class RunStageResponse(BaseModel):
    run_id: str
    stage: StageName
    status: Literal["success", "failed"]
    qc: dict[str, Any] | None = None
    error: str | None = None

