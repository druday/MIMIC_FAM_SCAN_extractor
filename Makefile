PYTHON ?= python3
RUN_NAME ?=

.PHONY: pre_llm_pipeline api_dev frontend_dev
pre_llm_pipeline:
	PYTHONPATH=src $(PYTHON) -m mimic_repro.pipeline --config config/pre_llm_config.json $(if $(RUN_NAME),--run-name $(RUN_NAME),)

api_dev:
	PYTHONPATH=src $(PYTHON) -m uvicorn backend_api.main:app --reload --port 8001

frontend_dev:
	cd frontend && npm run dev

