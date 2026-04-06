export type StageName = "stage1" | "stage2" | "stage3" | "stage4";

export type StageState = {
  status: "pending" | "running" | "success" | "failed";
  started_at: string | null;
  ended_at: string | null;
  error: string | null;
};

export type RunStatus = {
  run_id: string;
  created_at: string;
  updated_at: string;
  profile_name: string | null;
  config_path: string;
  config_snapshot_path: string;
  stages: Record<StageName, StageState>;
  outputs: Record<string, string>;
};

export type RunStageResponse = {
  run_id: string;
  stage: StageName;
  status: "success" | "failed";
  qc?: Record<string, unknown>;
  error?: string;
};

export type Profile = {
  profile_name: string;
  keyword_groups: Record<string, string[]>;
  icd_prefixes: string[];
  extract_regex?: string | null;
  trim_after_headers?: string[] | null;
};

export type ConfigOverrides = {
  family_history: {
    extract_regex: string;
    trim_after_headers: string[];
  };
  structured_data: {
    icd_prefixes: string[];
  };
  keywords: Record<string, string[]>;
  cohort: {
    refiners: {
      enabled: boolean;
      genders: string[];
      age_min: number | null;
      age_max: number | null;
      cancer_types: string[];
      note_length_min: number | null;
      note_length_max: number | null;
      notes_per_patient_min: number | null;
      notes_per_patient_max: number | null;
    };
  };
  garde_export?: { enabled: boolean };
  export_subset?: {
    enabled?: boolean;
    max_patients?: number;
    age_min?: number | null;
    age_max?: number | null;
    records_per_patient_min?: number | null;
    records_per_patient_max?: number | null;
    random_seed?: number;
  };
  llm?: {
    provider?: string;
    model?: string;
    temperature?: number;
    max_tokens?: number;
  };
};

