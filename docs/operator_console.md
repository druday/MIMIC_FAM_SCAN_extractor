# Operator Console Guide (React + FastAPI)

This console provides stage-by-stage orchestration for the strict pre-LLM reproducible pipeline.

## Components

- **Backend API:** `backend_api/main.py`
- **Frontend UI:** `frontend/`
- **Pipeline engine:** `src/mimic_repro/`

## API Endpoints

- `POST /runs` create run context and lock config snapshot.
- `POST /runs/{runId}/stage/{stageName}` execute `stage1`, `stage2`, or `stage3`.
- `GET /runs/{runId}/status` fetch stage status and errors.
- `GET /runs/{runId}/artifacts/qc` read `qc_summary.json`.
- `GET /runs/{runId}/artifacts/manifest` read `run_manifest.json`.
- `GET /runs/{runId}/artifacts/deviation` read `deviation_report.json`.
- `GET /runs/{runId}/artifacts/config` read `config_snapshot.json`.
- `GET /profiles` and `POST /profiles` manage reusable cancer profiles.

## Run Locally

1. Install Python dependencies:
   - `pip install -r requirements.txt`
2. Start API:
   - `make api_dev`
3. Start frontend:
   - `cd frontend && npm install && npm run dev`
4. Open browser at `http://localhost:5173`.

## Operator Workflow

1. Create run with run ID, config path, and optional profile.
2. Run `stage1`, review extraction and keyword metrics.
3. Run `stage2`, review refined keyword-positive cohort metrics (patients, records, notes-per-patient).
4. Run `stage3`, review ICD diagnostics and merged output.
5. Review deviation panel for notebook-visible vs strict rationale.
6. Export evidence paths from manifest and attach to manuscript supplement.

## Replication for Other Cancer Types

Use profile endpoints to define:
- `profile_name`
- `keyword_groups`
- `icd_prefixes`
- optional extraction overrides (`extract_regex`, `trim_after_headers`)

Apply profile at run creation to reuse the same strict reproducibility workflow.

