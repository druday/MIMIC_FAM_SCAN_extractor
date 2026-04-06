"""Generate strict pipeline vs notebook-visible deviation report."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from mimic_repro.io_utils import write_json


def _read_notebook_payload(notebook_path: Path) -> dict[str, Any]:
    return json.loads(notebook_path.read_text(encoding="utf-8"))


def _cell_output_text(cell: dict[str, Any]) -> str:
    output_chunks: list[str] = []
    for output in cell.get("outputs", []):
        if "text" in output:
            text = output["text"]
            output_chunks.append("".join(text) if isinstance(text, list) else str(text))
        if "data" in output and "text/plain" in output["data"]:
            text = output["data"]["text/plain"]
            output_chunks.append("".join(text) if isinstance(text, list) else str(text))
    return "\n".join(output_chunks)


def _read_notebook_outputs(notebook_path: Path) -> str:
    payload = _read_notebook_payload(notebook_path)
    output_chunks: list[str] = []
    for cell in payload.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        output_chunks.append(_cell_output_text(cell))
    return "\n".join(output_chunks)


def _extract_first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _extract_shape(pattern: str, text: str) -> tuple[int, int] | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _extract_shape_from_source_cell(
    notebook_path: Path,
    source_snippet: str,
) -> tuple[int, int] | None:
    payload = _read_notebook_payload(notebook_path)
    candidate_shapes: list[tuple[int, int]] = []
    for cell in payload.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if source_snippet not in source:
            continue
        output_text = _cell_output_text(cell)
        shape = _extract_shape(r"\((\d+),\s*(\d+)\)", output_text)
        if shape:
            candidate_shapes.append(shape)
    return candidate_shapes[-1] if candidate_shapes else None


def generate_deviation_report(
    project_root: Path,
    run_dir: Path,
) -> Path:
    """Write deviation report JSON and return its path."""
    notebook_1 = project_root / "Final 1 Family History Notes from MIMIC-Note.ipynb"
    notebook_2 = project_root / "Final 2 Family History Data from MIMIC-IV.ipynb"
    notebook_4 = project_root / "Final 4 LLM input data consolidation.ipynb"

    nb1_text = _read_notebook_outputs(notebook_1) if notebook_1.exists() else ""
    nb2_text = _read_notebook_outputs(notebook_2) if notebook_2.exists() else ""
    nb4_text = _read_notebook_outputs(notebook_4) if notebook_4.exists() else ""
    notebook_text = "\n".join([nb1_text, nb2_text, nb4_text])

    strict_cohort = pd.read_csv(run_dir / "keyword_positive_cohort.csv")
    strict_merged = pd.read_csv(run_dir / "merged_df.csv")

    merged_shape = (
        _extract_shape_from_source_cell(notebook_4, "merged_df.shape")
        if notebook_4.exists()
        else None
    )
    notebook_metrics = {
        "validated_subjects": _extract_first_int(r"Total number of patients:\s*(\d+)", notebook_text),
        "validated_notes": _extract_first_int(r"Total number of notes:\s*(\d+)", notebook_text),
        "merged_shape": merged_shape,
    }
    strict_metrics = {
        "validated_subjects": int(strict_cohort["subject_id"].nunique(dropna=True)),
        "validated_notes": int(len(strict_cohort)),
        "merged_shape": (int(strict_merged.shape[0]), int(strict_merged.shape[1])),
    }

    deviations: list[dict[str, Any]] = []
    if notebook_metrics["validated_subjects"] is not None and (
        notebook_metrics["validated_subjects"] != strict_metrics["validated_subjects"]
    ):
        deviations.append(
            {
                "metric": "validated_subjects",
                "notebook_visible": notebook_metrics["validated_subjects"],
                "strict_pipeline": strict_metrics["validated_subjects"],
                "rationale": (
                    "Strict pipeline builds cohort from keyword-positive family-history notes "
                    "without legacy validation-file filtering."
                ),
            }
        )
    if notebook_metrics["validated_notes"] is not None and (
        notebook_metrics["validated_notes"] != strict_metrics["validated_notes"]
    ):
        deviations.append(
            {
                "metric": "validated_notes",
                "notebook_visible": notebook_metrics["validated_notes"],
                "strict_pipeline": strict_metrics["validated_notes"],
                "rationale": (
                    "Strict pipeline carries all keyword-positive notes for all keyword-positive subjects; "
                    "notebook flow used a legacy validated subset."
                ),
            }
        )
    if notebook_metrics["merged_shape"] is not None and (
        notebook_metrics["merged_shape"] != strict_metrics["merged_shape"]
    ):
        deviations.append(
            {
                "metric": "merged_shape",
                "notebook_visible": notebook_metrics["merged_shape"],
                "strict_pipeline": strict_metrics["merged_shape"],
                "rationale": (
                    "Strict pipeline filters diagnoses to family-history ICD prefixes "
                    "(V16/Z80) before merge; notebook merge keeps all diagnoses."
                ),
            }
        )

    payload = {
        "notebook_metrics_visible_outputs": notebook_metrics,
        "strict_pipeline_metrics": strict_metrics,
        "deviations": deviations,
        "interpretation": (
            "Differences are intentional strict-design effects unless a metric diverges without "
            "a documented rationale."
        ),
    }
    report_path = run_dir / "deviation_report.json"
    write_json(report_path, payload)
    return report_path

