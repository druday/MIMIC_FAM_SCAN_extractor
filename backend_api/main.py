"""FastAPI entrypoint for pipeline operator console."""

from __future__ import annotations

from pathlib import Path
import sys

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend_api.models import (
    CreateProfileRequest,
    CreateRunRequest,
    RunAllRequest,
    RunStageRequest,
    RunStageResponse,
    StageName,
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backend_api.service import PipelineService

service = PipelineService(project_root=PROJECT_ROOT)

app = FastAPI(title="MIMIC Pipeline Operator API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs")
def create_run(request: CreateRunRequest) -> dict:
    try:
        return service.create_run(request)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/runs/{run_id}/stage/{stage_name}", response_model=RunStageResponse)
def run_stage(
    run_id: str,
    stage_name: StageName,
    request: RunStageRequest = Body(default_factory=RunStageRequest),
) -> RunStageResponse:
    try:
        overrides = request.config_overrides if request.config_overrides else None
        payload = service.run_stage(run_id=run_id, stage=stage_name, config_overrides=overrides)
        return RunStageResponse(**payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/runs/{run_id}/run-all", response_model=RunStageResponse)
def run_all(
    run_id: str,
    request: RunAllRequest = Body(default_factory=RunAllRequest),
) -> RunStageResponse:
    try:
        overrides = request.config_overrides if request.config_overrides else None
        payload = service.run_all_stages(run_id=run_id, stage4_config_overrides=overrides)
        return RunStageResponse(**payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/runs/{run_id}/status")
def run_status(run_id: str) -> dict:
    try:
        return service.get_status(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/runs/{run_id}/artifacts/{artifact_name}")
def run_artifact(run_id: str, artifact_name: str) -> dict:
    try:
        return service.read_artifact(run_id, artifact_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/profiles")
def list_profiles() -> list[dict]:
    return service.list_profiles()


@app.post("/profiles")
def create_profile(request: CreateProfileRequest) -> dict:
    try:
        return service.create_profile(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

