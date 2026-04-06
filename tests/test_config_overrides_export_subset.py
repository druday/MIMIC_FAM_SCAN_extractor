"""API service: config_overrides must merge export_subset.max_patients into the active config for stage 4."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend_api.service import PipelineService


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_apply_config_overrides_sets_max_patients_from_ui(project_root: Path):
    svc = PipelineService(project_root)
    base = {
        "export_subset": {
            "enabled": True,
            "max_patients": 250,
            "age_min": None,
            "age_max": None,
            "records_per_patient_min": None,
            "records_per_patient_max": None,
            "random_seed": 42,
        },
        "family_history": {"subject_id_column": "subject_id"},
    }
    merged = svc._apply_config_overrides(
        base,
        {
            "export_subset": {
                "enabled": True,
                "max_patients": 10,
                "age_min": None,
                "age_max": None,
                "records_per_patient_min": None,
                "records_per_patient_max": None,
            },
        },
    )
    assert merged["export_subset"]["max_patients"] == 10


def test_apply_config_overrides_preserves_false_enabled(project_root: Path):
    svc = PipelineService(project_root)
    base = {
        "export_subset": {"enabled": True, "max_patients": 250},
        "family_history": {"subject_id_column": "subject_id"},
    }
    merged = svc._apply_config_overrides(
        base,
        {"export_subset": {"enabled": False, "max_patients": 10}},
    )
    assert merged["export_subset"]["enabled"] is False
