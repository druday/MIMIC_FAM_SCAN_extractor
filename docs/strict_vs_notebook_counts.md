# How to Interpret Strict vs Notebook Counts

This project intentionally keeps a **strict pre-LLM cohort** for reproducibility submission.

## Why strict counts are smaller

1. Strict pipeline keeps only notes with cancer-keyword-positive family-history content.
2. Strict pipeline keeps **all** keyword-positive subjects and **all** keyword-positive notes (no legacy validation-file filter).
3. Structured merge applies family-history ICD prefix filtering (`V16`, `Z80`) before merge output.

Notebook outputs may look larger because some notebook paths:
- keep broader note pools in memory, and
- apply ICD filtering later for only specific derived fields.

## What to use in manuscript reproducibility package

- Use strict run artifacts under `artifacts/pre_llm/<run_id>/`.
- Use:
  - `qc_summary.json` for stage-level counts and quality checks,
  - `deviation_report.json` for notebook-visible vs strict comparison.

## Reviewer-facing framing

- Larger notebook counts are historical workflow behavior.
- Strict pipeline counts are submission-standard deterministic outputs.
- Deviations are documented and intentional unless flagged as unexplained in `deviation_report.json`.

