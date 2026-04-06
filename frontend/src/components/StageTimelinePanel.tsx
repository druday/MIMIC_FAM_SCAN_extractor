import React, { useEffect, useRef, useState } from "react";

import type { RunStatus, StageName } from "../types";

const STAGES: { name: StageName; title: string }[] = [
  { name: "stage1", title: "Stage 1 - Extract + Keywords" },
  { name: "stage2", title: "Stage 2 - Build Keyword Cohort" },
  { name: "stage3", title: "Stage 3 - Merge Structured Data" },
  { name: "stage4", title: "Stage 4 - GARDE Export" },
];

/** Matches backend merge for Stage 4 / Run All (stage 4 leg). */
function buildExportSubsetConfigOverrides(input: {
  exportSubsetEnabled: boolean;
  maxPatientsText: string;
  exportAgeMinText: string;
  exportAgeMaxText: string;
  recordsPerPatientMinText: string;
  recordsPerPatientMaxText: string;
}): Record<string, unknown> {
  const rawMax =
    input.maxPatientsText.trim() === "" ? 250 : Number(input.maxPatientsText.trim());
  const max_patients =
    Number.isFinite(rawMax) && rawMax > 0 ? Math.floor(rawMax) : 250;
  const numOrNull = (s: string): number | null => {
    if (s.trim() === "") return null;
    const n = Number(s.trim());
    return Number.isFinite(n) ? n : null;
  };
  return {
    export_subset: {
      enabled: input.exportSubsetEnabled,
      max_patients,
      age_min: numOrNull(input.exportAgeMinText),
      age_max: numOrNull(input.exportAgeMaxText),
      records_per_patient_min: numOrNull(input.recordsPerPatientMinText),
      records_per_patient_max: numOrNull(input.recordsPerPatientMaxText),
    },
  };
}

type Props = {
  runStatus: RunStatus | null;
  runningStage: StageName | null;
  onRunStage: (stage: StageName, configOverrides?: Record<string, unknown>) => void;
  onRunAll: (configOverrides?: Record<string, unknown>) => void;
  qcSummary: Record<string, unknown> | null;
  deviation: Record<string, unknown> | null;
  manifest: Record<string, unknown> | null;
  configSnapshot: Record<string, unknown> | null;
};

function readNumber(value: unknown): string {
  if (typeof value === "number") return value.toLocaleString();
  return "n/a";
}

function renderMetricRow(label: string, value: unknown) {
  return (
    <div className="stageMetricRow" key={label}>
      <span className="muted">{label}</span>
      <strong>{readNumber(value)}</strong>
    </div>
  );
}

function outputRow(label: string, path: string) {
  const copyPath = async () => {
    try {
      await navigator.clipboard.writeText(path);
    } catch {
      // No-op fallback keeps UI functional in restricted contexts.
    }
  };
  return (
    <div className="outputRow" key={label}>
      <div>
        <div>{label}</div>
        <code>{path}</code>
      </div>
      <button onClick={copyPath}>Copy path</button>
    </div>
  );
}

function metricCard(title: string, value: string | number) {
  return (
    <div className="metricCard" key={title}>
      <div className="muted">{title}</div>
      <div className="metric">{value}</div>
    </div>
  );
}

export function StageTimelinePanel({ runStatus, runningStage, onRunStage, onRunAll, qcSummary, deviation, manifest, configSnapshot }: Props) {
  const [exportSubsetEnabled, setExportSubsetEnabled] = useState(true);
  const [maxPatientsText, setMaxPatientsText] = useState("250");
  const [exportAgeMinText, setExportAgeMinText] = useState("");
  const [exportAgeMaxText, setExportAgeMaxText] = useState("");
  const [recordsPerPatientMinText, setRecordsPerPatientMinText] = useState("");
  const [recordsPerPatientMaxText, setRecordsPerPatientMaxText] = useState("");
  /** Do not re-sync from config on every artifact refresh — that overwrote user-entered cohort size (e.g. 10 → 250). */
  const exportFormSyncedForRunId = useRef<string | null>(null);

  useEffect(() => {
    const runId = runStatus?.run_id ?? null;
    if (!runId) {
      exportFormSyncedForRunId.current = null;
      return;
    }
    if (!configSnapshot) return;
    if (exportFormSyncedForRunId.current === runId) return;
    exportFormSyncedForRunId.current = runId;
    const cfg = (configSnapshot.export_subset as Record<string, unknown>) ?? {};
    setExportSubsetEnabled(cfg.enabled !== false);
    setMaxPatientsText(String(cfg.max_patients ?? 250));
    setExportAgeMinText(cfg.age_min != null ? String(cfg.age_min) : "");
    setExportAgeMaxText(cfg.age_max != null ? String(cfg.age_max) : "");
    setRecordsPerPatientMinText(cfg.records_per_patient_min != null ? String(cfg.records_per_patient_min) : "");
    setRecordsPerPatientMaxText(cfg.records_per_patient_max != null ? String(cfg.records_per_patient_max) : "");
  }, [runStatus?.run_id, configSnapshot]);
  const stage1Qc =
    (qcSummary?.stage1_extract_family_history_notes as Record<string, unknown>) ?? null;
  const stage2Qc =
    (qcSummary?.stage2_build_validated_cohort as Record<string, unknown>) ?? null;
  const stage3Qc =
    (qcSummary?.stage3_merge_structured_mimic as Record<string, unknown>) ?? null;
  const stage4Qc =
    (qcSummary?.stage4_garde_export as Record<string, unknown>) ?? null;
  const allStageNames: StageName[] = ["stage1", "stage2", "stage3", "stage4"];
  const completedStages = runStatus
    ? allStageNames.filter((name) => runStatus.stages[name]?.status === "success").length
    : 0;
  const nextStage =
    runStatus && allStageNames.find((name) => runStatus.stages[name]?.status !== "success");
  const canRunAll = runStatus && nextStage && runningStage === null;
  const isRunningAll = runningStage !== null;

  const s1 = (qcSummary?.stage1_extract_family_history_notes as Record<string, unknown>) ?? {};
  const s2 = (qcSummary?.stage2_build_validated_cohort as Record<string, unknown>) ?? {};
  const s3 = (qcSummary?.stage3_merge_structured_mimic as Record<string, unknown>) ?? {};
  const s4 = (qcSummary?.stage4_garde_export as Record<string, unknown>) ?? {};
  const s1Lineage = (s1.lineage as Record<string, unknown>) ?? {};
  const s2Lineage = (s2.lineage as Record<string, unknown>) ?? {};
  const s4a = (s4.stage4a as Record<string, unknown>) ?? {};
  const s4d = (s4.stage4d as Record<string, unknown>) ?? {};
  const s4Subset = (s4.stage4_subset as Record<string, unknown>) ?? null;
  const deviations = (deviation?.deviations as Array<Record<string, unknown>>) ?? [];
  const outputs = (manifest?.outputs as Record<string, unknown>) ?? {};

  return (
    <section className="panel">
      <h2>Step 2: Run Pipeline</h2>
      {!runStatus && <p className="muted">Create a run first (Step 1).</p>}
      {runStatus && (
        <>
          <div className="runSummary">
            <strong>Progress: {completedStages}/4 stages complete</strong>
            <div className="muted">Outputs: <code>artifacts/pre_llm/{runStatus.run_id}</code></div>
            {nextStage ? (
              <div className="muted">Next: run {nextStage} or run all remaining stages.</div>
            ) : (
              <div className="muted">All stages complete. Review outputs below.</div>
            )}
          </div>
          {canRunAll && (
            <button
              className="primaryButton"
              onClick={() =>
                onRunAll(
                  buildExportSubsetConfigOverrides({
                    exportSubsetEnabled,
                    maxPatientsText,
                    exportAgeMinText,
                    exportAgeMaxText,
                    recordsPerPatientMinText,
                    recordsPerPatientMaxText,
                  })
                )
              }
              disabled={isRunningAll}
            >
              Run All Stages
            </button>
          )}
          {qcSummary && (
            <>
              {runStatus?.stages.stage4?.status === "success" && s4 && s4.stage4_subset == null && (
                <p className="error" style={{ marginTop: "1rem" }}>
                  <strong>Export subset did not run</strong> for this Stage 4 (QC has no{" "}
                  <code>stage4_subset</code>). An older API process may have run before subset support;
                  outputs used the <strong>full cohort</strong>. Restart the backend from the current
                  codebase, set max patients, then <strong>Re-run Stage 4</strong>.
                </p>
              )}
            <div className="metricsGrid" style={{ marginTop: "1rem" }}>
              {metricCard("Keyword-positive subjects", Number(s1Lineage.keyword_positive_subjects ?? 0))}
              {metricCard("Cohort subjects", Number(s2Lineage.final_strict_subjects ?? 0))}
              {s4Subset && s4Subset.subset_applied === false && (
                metricCard("Export subset", "Off (full cohort)")
              )}
              {s4Subset && s4Subset.subset_applied !== false && (
                metricCard(
                  "Export subset",
                  `${Number(s4Subset.subjects_after ?? 0)} of ${Number(s4Subset.subjects_before ?? 0)}`
                )
              )}
              {metricCard("GARDE demographics", Number(s4a.demographics_rows ?? 0))}
              {metricCard("GARDE family history", Number(s4d.family_history_rows ?? 0))}
            </div>
            </>
          )}
          {STAGES.map((stage) => {
          const showExportSubsetBeforeStage4 =
            stage.name === "stage4" &&
            runStatus?.stages.stage3?.status === "success" &&
            runStatus?.stages.stage4?.status !== "success";
          const state = runStatus.stages[stage.name];
          const canRun =
            stage.name === "stage1"
              ? true
              : stage.name === "stage2"
              ? runStatus.stages.stage1?.status === "success"
              : stage.name === "stage3"
              ? runStatus.stages.stage1?.status === "success" && runStatus.stages.stage2?.status === "success"
              : runStatus.stages.stage1?.status === "success" && runStatus.stages.stage2?.status === "success" && runStatus.stages.stage3?.status === "success";
          const stageOutputs =
            stage.name === "stage1"
              ? [
                  { label: "Extracted family history notes", path: runStatus.outputs.stage1_notes },
                  { label: "Keyword-positive family history notes", path: runStatus.outputs.stage1_keyword_positive },
                ]
              : stage.name === "stage2"
              ? [{ label: "Keyword-positive cohort notes", path: runStatus.outputs.stage2_keyword_cohort }]
              : stage.name === "stage3"
              ? [
                  { label: "Merged structured output", path: runStatus.outputs.stage3_merged },
                  { label: "QC summary", path: runStatus.outputs.qc_summary },
                  { label: "Run manifest", path: runStatus.outputs.run_manifest },
                  { label: "Deviation report", path: runStatus.outputs.deviation_report },
                ]
              : [
                  { label: "GARDE demographics", path: runStatus.outputs.stage4_garde_demographics ?? "" },
                  { label: "GARDE family history", path: runStatus.outputs.stage4_garde_family_history ?? "" },
                ];
          const stageDescription =
            stage.name === "stage1"
              ? "Extract Family History sections from discharge notes and apply configured cancer keywords."
              : stage.name === "stage2"
              ? "Build strict cohort from all keyword-positive subjects and all keyword-positive notes."
              : stage.name === "stage3"
              ? "Join strict cohort subjects with admissions, diagnoses, and patients using ICD prefix filtering."
              : "Generate GARDE demographics CSV, consolidate FH notes, apply LLM imputation, and export GARDE family history CSV.";
          const stageMetrics =
            stage.name === "stage1"
              ? [
                  renderMetricRow(
                    "Extracted notes rows",
                    (stage1Qc?.extracted_notes as Record<string, unknown> | undefined)?.rows
                  ),
                  renderMetricRow(
                    "Keyword-positive notes rows",
                    (stage1Qc?.keyword_positive_notes as Record<string, unknown> | undefined)?.rows
                  ),
                  renderMetricRow(
                    "Extracted subjects",
                    (stage1Qc?.lineage as Record<string, unknown> | undefined)?.extracted_subjects
                  ),
                  renderMetricRow(
                    "Keyword-positive subjects",
                    (stage1Qc?.lineage as Record<string, unknown> | undefined)?.keyword_positive_subjects
                  ),
                  renderMetricRow(
                    "Subjects dropped after keyword filter",
                    (stage1Qc?.lineage as Record<string, unknown> | undefined)?.subjects_dropped_after_keyword_filter
                  ),
                ]
              : stage.name === "stage2"
              ? [
                  renderMetricRow(
                    "Keyword-positive notes",
                    (stage2Qc?.lineage as Record<string, unknown> | undefined)?.keyword_positive_notes
                  ),
                  renderMetricRow(
                    "Final family history records",
                    (stage2Qc?.lineage as Record<string, unknown> | undefined)?.final_family_history_records
                  ),
                  renderMetricRow(
                    "Final strict cohort subjects",
                    (stage2Qc?.lineage as Record<string, unknown> | undefined)?.final_strict_subjects
                  ),
                  renderMetricRow(
                    "Keyword-positive subjects",
                    (stage2Qc?.lineage as Record<string, unknown> | undefined)?.keyword_positive_subjects
                  ),
                  renderMetricRow(
                    "Notes per subject average",
                    (stage2Qc as Record<string, unknown> | undefined)?.notes_per_subject_avg
                  ),
                  renderMetricRow(
                    "Notes per patient min",
                    (stage2Qc?.lineage as Record<string, unknown> | undefined)?.final_notes_per_patient_min
                  ),
                  renderMetricRow(
                    "Notes per patient max",
                    (stage2Qc?.lineage as Record<string, unknown> | undefined)?.final_notes_per_patient_max
                  ),
                  renderMetricRow(
                    "Note length min (chars)",
                    (stage2Qc?.lineage as Record<string, unknown> | undefined)?.final_note_length_min
                  ),
                  renderMetricRow(
                    "Note length max (chars)",
                    (stage2Qc?.lineage as Record<string, unknown> | undefined)?.final_note_length_max
                  ),
                ]
              : stage.name === "stage3"
              ? [
                  renderMetricRow(
                    "Admissions filtered rows",
                    (stage3Qc?.admissions_filtered as Record<string, unknown> | undefined)?.rows
                  ),
                  renderMetricRow(
                    "Diagnoses before ICD filter",
                    (stage3Qc?.icd_filter_diagnostics as Record<string, unknown> | undefined)
                      ?.diagnoses_rows_before_prefix_filter
                  ),
                  renderMetricRow(
                    "Diagnoses after ICD filter",
                    (stage3Qc?.icd_filter_diagnostics as Record<string, unknown> | undefined)
                      ?.diagnoses_rows_after_prefix_filter
                  ),
                  renderMetricRow(
                    "Subjects before ICD filter",
                    (stage3Qc?.icd_filter_diagnostics as Record<string, unknown> | undefined)
                      ?.diagnoses_subjects_before_prefix_filter
                  ),
                  renderMetricRow(
                    "Subjects after ICD filter",
                    (stage3Qc?.icd_filter_diagnostics as Record<string, unknown> | undefined)
                      ?.diagnoses_subjects_after_prefix_filter
                  ),
                  renderMetricRow(
                    "Merged output rows",
                    (stage3Qc?.merged_output as Record<string, unknown> | undefined)?.rows
                  ),
                ]
              : [
                  renderMetricRow(
                    "Demographics rows",
                    (stage4Qc?.["stage4a"] as Record<string, unknown> | undefined)?.demographics_rows
                  ),
                  renderMetricRow(
                    "Demographics subjects",
                    (stage4Qc?.["stage4a"] as Record<string, unknown> | undefined)?.demographics_subjects
                  ),
                  renderMetricRow(
                    "Consolidated subjects",
                    (stage4Qc?.["stage4b"] as Record<string, unknown> | undefined)?.consolidated_subjects
                  ),
                  renderMetricRow(
                    "Imputed count",
                    (stage4Qc?.["stage4c"] as Record<string, unknown> | undefined)?.imputed_count
                  ),
                  renderMetricRow(
                    "API errors",
                    (stage4Qc?.["stage4c"] as Record<string, unknown> | undefined)?.api_error_count
                  ),
                  renderMetricRow(
                    "Placeholders after",
                    (stage4Qc?.["stage4c"] as Record<string, unknown> | undefined)?.placeholders_total_after
                  ),
                  renderMetricRow(
                    "Rows w/ placeholders left",
                    (stage4Qc?.["stage4c"] as Record<string, unknown> | undefined)?.rows_with_remaining_placeholders
                  ),
                  renderMetricRow(
                    "Imputation partial",
                    String((stage4Qc?.["stage4c"] as Record<string, unknown> | undefined)?.imputation_partial ?? "")
                  ),
                  renderMetricRow(
                    "Imputation skipped",
                    (stage4Qc?.["stage4c"] as Record<string, unknown> | undefined)?.imputation_skipped
                  ),
                  renderMetricRow(
                    "Family history rows",
                    (stage4Qc?.["stage4d"] as Record<string, unknown> | undefined)?.family_history_rows
                  ),
                  renderMetricRow(
                    "Family history subjects",
                    (stage4Qc?.["stage4d"] as Record<string, unknown> | undefined)?.family_history_subjects
                  ),
                  renderMetricRow(
                    "Rows dropped over length",
                    (stage4Qc?.["stage4d"] as Record<string, unknown> | undefined)?.rows_dropped_over_length
                  ),
                  renderMetricRow(
                    "FH CSV columns",
                    (stage4Qc?.["stage4d"] as Record<string, unknown> | undefined)?.schema_columns
                  ),
                  renderMetricRow(
                    "FH column contract",
                    String((stage4Qc?.["stage4d"] as Record<string, unknown> | undefined)?.column_order ?? "")
                  ),
                ];

          return (
            <React.Fragment key={stage.name}>
              {showExportSubsetBeforeStage4 && (
                <div className="stageCard" style={{ marginTop: "1rem", borderColor: "#3b82f6" }}>
                  <div>
                    <strong>Export subset (before Stage 4)</strong>
                    <p className="muted" style={{ marginTop: "0.25rem" }}>
                    Select cohort size and filters. LLM imputation runs only on this subset (reduces cost).
                    These settings apply when you run Stage 4 or <strong>Run All Stages</strong> (stage 4 leg).
                  </p>
                    <div className="grid" style={{ marginTop: "0.75rem" }}>
                      <label>
                        Enable subset
                        <select value={exportSubsetEnabled ? "yes" : "no"} onChange={(e) => setExportSubsetEnabled(e.target.value === "yes")}>
                          <option value="yes">Yes</option>
                          <option value="no">No (use full cohort)</option>
                        </select>
                      </label>
                      <label>
                        Max patients
                        <input value={maxPatientsText} onChange={(e) => setMaxPatientsText(e.target.value)} placeholder="250" />
                      </label>
                      <label>
                        Age min
                        <input value={exportAgeMinText} onChange={(e) => setExportAgeMinText(e.target.value)} placeholder="e.g. 18" />
                      </label>
                      <label>
                        Age max
                        <input value={exportAgeMaxText} onChange={(e) => setExportAgeMaxText(e.target.value)} placeholder="e.g. 80" />
                      </label>
                      <label>
                        Records/patient min
                        <input value={recordsPerPatientMinText} onChange={(e) => setRecordsPerPatientMinText(e.target.value)} placeholder="e.g. 1" />
                      </label>
                      <label>
                        Records/patient max
                        <input value={recordsPerPatientMaxText} onChange={(e) => setRecordsPerPatientMaxText(e.target.value)} placeholder="e.g. 100" />
                      </label>
                    </div>
                  </div>
                </div>
              )}
            <div key={stage.name} className="stageCard">
              <div>
                <strong>{stage.title}</strong>
                <div>Status: {state.status}</div>
                {state.error && <div className="error">Error: {state.error}</div>}
                <div className="stageDescription">{stageDescription}</div>
                {state.status === "success" && (
                  <div className="stageDetails">
                    <h4>Stage results</h4>
                    <div className="stageMetrics">{stageMetrics}</div>
                    <h4>Outputs created</h4>
                    <div className="outputList">{stageOutputs.map((entry) => outputRow(entry.label, entry.path))}</div>
                  </div>
                )}
              </div>
              <button
                disabled={!canRun || runningStage !== null}
                onClick={() => {
                  if (stage.name === "stage4" && runStatus?.stages.stage3?.status === "success") {
                    onRunStage(
                      stage.name,
                      buildExportSubsetConfigOverrides({
                        exportSubsetEnabled,
                        maxPatientsText,
                        exportAgeMinText,
                        exportAgeMaxText,
                        recordsPerPatientMinText,
                        recordsPerPatientMaxText,
                      })
                    );
                  } else {
                    onRunStage(stage.name);
                  }
                }}
              >
                {runningStage === stage.name ? "Running..." : state.status === "success" ? "Re-run Stage" : "Run Stage"}
              </button>
            </div>
            </React.Fragment>
          );
        })}
          {runStatus?.stages.stage3?.status === "success" && (
            <details className="customizeDetails" style={{ marginTop: "1rem" }}>
              <summary>Deviation report & evidence paths</summary>
              <div className="customizeContent">
                {deviations.length === 0 && Object.keys(outputs).length === 0 && (
                  <p className="muted">Available after Stage 3. Refresh to load.</p>
                )}
                {deviations.length > 0 && (
                  <>
                    <h3>Notebook vs Strict Deviations</h3>
                    {deviations.map((entry, idx) => (
                      <div key={idx} className="stageCard">
                        <div>
                          <strong>{String(entry.metric)}</strong>
                          <div>Notebook-visible: <code>{JSON.stringify(entry.notebook_visible)}</code></div>
                          <div>Strict pipeline: <code>{JSON.stringify(entry.strict_pipeline)}</code></div>
                          <div className="muted">{String(entry.rationale)}</div>
                        </div>
                      </div>
                    ))}
                  </>
                )}
                {Object.keys(outputs).length > 0 && (
                  <>
                    <h3>Evidence Bundle Paths</h3>
                    <pre className="jsonBlock">{JSON.stringify(outputs, null, 2)}</pre>
                  </>
                )}
              </div>
            </details>
          )}
        </>
      )}
    </section>
  );
}

