"""HTTP layer: POST body must pass export_subset into the service (regression: UI cohort size)."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

import backend_api.main as main


def test_post_stage4_json_body_exports_subset_max_patients_to_service():
    client = TestClient(main.app)
    payload = {
        "config_overrides": {
            "export_subset": {
                "enabled": True,
                "max_patients": 10,
                "age_min": None,
                "age_max": None,
                "records_per_patient_min": None,
                "records_per_patient_max": None,
            }
        }
    }
    with patch.object(
        main.service,
        "run_stage",
        return_value={
            "run_id": "test_run",
            "stage": "stage4",
            "status": "success",
            "qc": {"stage4_subset": {"subjects_after": 10}},
            "error": None,
        },
    ) as m_run:
        response = client.post("/runs/test_run/stage/stage4", json=payload)
        assert response.status_code == 200, response.text
        kwargs = m_run.call_args.kwargs
        assert kwargs["config_overrides"]["export_subset"]["max_patients"] == 10


def test_post_stage4_empty_body_is_allowed():
    client = TestClient(main.app)
    with patch.object(
        main.service,
        "run_stage",
        return_value={
            "run_id": "test_run",
            "stage": "stage4",
            "status": "success",
            "qc": {},
            "error": None,
        },
    ) as m_run:
        response = client.post("/runs/test_run/stage/stage4", json={})
        assert response.status_code == 200, response.text
        kwargs = m_run.call_args.kwargs
        assert kwargs["config_overrides"] is None
