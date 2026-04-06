import { useEffect, useState } from "react";

import { createProfile, createRun, getArtifact, getRunStatus, listProfiles, runAllStages, runStage } from "./api";
import { ProfilesPanel } from "./components/ProfilesPanel";
import { RunSetupPanel } from "./components/RunSetupPanel";
import { StageTimelinePanel } from "./components/StageTimelinePanel";
import type { ConfigOverrides, Profile, RunStatus, StageName } from "./types";

export default function App() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [qcSummary, setQcSummary] = useState<Record<string, unknown> | null>(null);
  const [manifest, setManifest] = useState<Record<string, unknown> | null>(null);
  const [deviation, setDeviation] = useState<Record<string, unknown> | null>(null);
  const [configSnapshot, setConfigSnapshot] = useState<Record<string, unknown> | null>(null);
  const [runningStage, setRunningStage] = useState<StageName | null>(null);
  const [message, setMessage] = useState<string>("Ready.");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listProfiles()
      .then(setProfiles)
      .catch((err) => setMessage(`Profiles load warning: ${String(err)}`));
  }, []);

  async function refreshArtifacts(runId: string) {
    const [qc, man, cfg] = await Promise.all([
      getArtifact(runId, "qc").catch(() => null),
      getArtifact(runId, "manifest").catch(() => null),
      getArtifact(runId, "config").catch(() => null),
    ]);
    setQcSummary(qc);
    setManifest(man);
    setConfigSnapshot(cfg);
    const dev = await getArtifact(runId, "deviation").catch(() => null);
    setDeviation(dev);
  }

  async function handleCreateRun(input: {
    runId: string;
    configPath: string;
    profileName?: string;
    configOverrides?: ConfigOverrides;
  }) {
    try {
      setBusy(true);
      const status = await createRun({
        run_id: input.runId,
        config_path: input.configPath,
        profile_name: input.profileName,
        config_overrides: input.configOverrides,
      });
      setRunStatus(status);
      setQcSummary(null);
      setManifest(null);
      setDeviation(null);
      setConfigSnapshot(null);
      setMessage(`Run ${status.run_id} created.`);
      await refreshArtifacts(status.run_id);
    } catch (err) {
      setMessage(`Create run failed: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleRunStage(stage: StageName, configOverrides?: Record<string, unknown>) {
    if (!runStatus) return;
    try {
      setRunningStage(stage);
      setMessage(`Running ${stage}...`);
      const result = await runStage(runStatus.run_id, stage, configOverrides);
      const latestStatus = await getRunStatus(runStatus.run_id);
      setRunStatus(latestStatus);
      await refreshArtifacts(runStatus.run_id);
      if (result.status === "success") {
        setMessage(`${stage} completed successfully.`);
      } else {
        setMessage(`${stage} failed: ${result.error ?? "unknown error"}`);
      }
    } catch (err) {
      setMessage(`Stage execution failed: ${String(err)}`);
    } finally {
      setRunningStage(null);
    }
  }

  async function handleRunAll(configOverrides?: Record<string, unknown>) {
    if (!runStatus) return;
    try {
      setRunningStage("stage1");
      setMessage("Running all stages...");
      const result = await runAllStages(runStatus.run_id, configOverrides);
      const latestStatus = await getRunStatus(runStatus.run_id);
      setRunStatus(latestStatus);
      await refreshArtifacts(runStatus.run_id);
      if (result.status === "success") {
        setMessage("All stages completed successfully.");
      } else {
        setMessage(`Pipeline failed at ${result.stage ?? "unknown"}: ${result.error ?? "unknown error"}`);
      }
    } catch (err) {
      setMessage(`Run all failed: ${String(err)}`);
    } finally {
      setRunningStage(null);
    }
  }

  async function handleCreateProfile(profile: Profile) {
    try {
      setBusy(true);
      await createProfile(profile);
      const updated = await listProfiles();
      setProfiles(updated);
      setMessage(`Profile ${profile.profile_name} saved.`);
    } catch (err) {
      setMessage(`Profile save failed: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  const hasPendingStage = runStatus && ["stage1", "stage2", "stage3", "stage4"].some(
    (s) => runStatus.stages[s as keyof typeof runStatus.stages]?.status === "pending"
  );
  const step = !runStatus ? 1 : hasPendingStage ? 2 : 3;

  return (
    <main className="app">
      <header>
        <h1>MIMIC Reproducible Pipeline Operator Console</h1>
        <p>
          Run the strict pipeline sequentially, compare against notebook-visible outputs, and export
          reproducibility evidence.
        </p>
        <nav className="workflowSteps">
          <span className={step === 1 ? "workflowStepActive" : "workflowStep"}>Step 1: Create Run</span>
          <span className="workflowStepArrow">→</span>
          <span className={step === 2 ? "workflowStepActive" : "workflowStep"}>Step 2: Run Pipeline</span>
          <span className="workflowStepArrow">→</span>
          <span className={step === 3 ? "workflowStepActive" : "workflowStep"}>Step 3: Review Outputs</span>
        </nav>
        <div className="statusBanner">{message}</div>
      </header>

      <RunSetupPanel profiles={profiles} onCreateRun={handleCreateRun} busy={busy || runningStage !== null} />
      <StageTimelinePanel
        runStatus={runStatus}
        runningStage={runningStage}
        onRunStage={handleRunStage}
        onRunAll={handleRunAll}
        qcSummary={qcSummary}
        deviation={deviation}
        manifest={manifest}
        configSnapshot={configSnapshot}
      />
      <details className="customizeDetails" style={{ marginTop: "1rem" }}>
        <summary>Profiles (manage cancer profiles)</summary>
        <div className="customizeContent">
          <ProfilesPanel profiles={profiles} onCreateProfile={handleCreateProfile} busy={busy || runningStage !== null} />
        </div>
      </details>
    </main>
  );
}

