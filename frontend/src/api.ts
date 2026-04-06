import type { ConfigOverrides, Profile, RunStageResponse, RunStatus, StageName } from "./types";

const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (import.meta.env.DEV ? "/api" : "http://127.0.0.1:8001");

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function createRun(payload: {
  run_id: string;
  config_path: string;
  profile_name?: string | null;
  config_overrides?: ConfigOverrides;
}): Promise<RunStatus> {
  const response = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse<RunStatus>(response);
}

export async function getRunStatus(runId: string): Promise<RunStatus> {
  const response = await fetch(`${API_BASE}/runs/${runId}/status`);
  return parseResponse<RunStatus>(response);
}

export async function runStage(
  runId: string,
  stageName: StageName,
  configOverrides?: Record<string, unknown>
): Promise<RunStageResponse> {
  const response = await fetch(`${API_BASE}/runs/${runId}/stage/${stageName}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(configOverrides ? { config_overrides: configOverrides } : {}),
  });
  return parseResponse<RunStageResponse>(response);
}

export async function runAllStages(
  runId: string,
  configOverrides?: Record<string, unknown>
): Promise<RunStageResponse> {
  const response = await fetch(`${API_BASE}/runs/${runId}/run-all`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(configOverrides ? { config_overrides: configOverrides } : {}),
  });
  return parseResponse<RunStageResponse>(response);
}

export async function getArtifact(
  runId: string,
  artifact: "qc" | "manifest" | "deviation" | "config"
) {
  const response = await fetch(`${API_BASE}/runs/${runId}/artifacts/${artifact}`);
  return parseResponse<Record<string, unknown>>(response);
}

export async function listProfiles(): Promise<Profile[]> {
  const response = await fetch(`${API_BASE}/profiles`);
  return parseResponse<Profile[]>(response);
}

export async function createProfile(profile: Profile): Promise<Profile> {
  const response = await fetch(`${API_BASE}/profiles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  return parseResponse<Profile>(response);
}

