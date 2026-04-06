import { useEffect, useMemo, useState } from "react";

import type { ConfigOverrides, Profile } from "../types";

type Props = {
  profiles: Profile[];
  onCreateRun: (input: {
    runId: string;
    configPath: string;
    profileName?: string;
    configOverrides?: ConfigOverrides;
  }) => void;
  busy: boolean;
};

export function RunSetupPanel({ profiles, onCreateRun, busy }: Props) {
  const [runId, setRunId] = useState(`console_run_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "_")}`);
  const [profileName, setProfileName] = useState<string>("");
  const [gardeExportEnabled, setGardeExportEnabled] = useState(true);
  const [customizeOpen, setCustomizeOpen] = useState(false);

  const [extractRegex, setExtractRegex] = useState("Family History:\\n(.*?)\\n\\n");
  const [trimHeadersText, setTrimHeadersText] = useState("Physical Exam:");
  const [icdPrefixesText, setIcdPrefixesText] = useState("V16\nZ80");
  const [refinersEnabled, setRefinersEnabled] = useState(false);
  const [gendersText, setGendersText] = useState("F\nM");
  const [ageMinText, setAgeMinText] = useState("");
  const [ageMaxText, setAgeMaxText] = useState("");
  const [noteLengthMinText, setNoteLengthMinText] = useState("");
  const [noteLengthMaxText, setNoteLengthMaxText] = useState("");
  const [notesPerPatientMinText, setNotesPerPatientMinText] = useState("");
  const [notesPerPatientMaxText, setNotesPerPatientMaxText] = useState("");
  const [cancerTypesText, setCancerTypesText] = useState("breast\novarian\ncolorectal");
  const [keywordText, setKeywordText] = useState<Record<string, string>>({
    breast: "",
    ovarian: "",
    colorectal: "",
  });
  const [llmProvider, setLlmProvider] = useState<"openai" | "azure">("openai");
  const [llmModel, setLlmModel] = useState("");
  const [exportSubsetEnabled, setExportSubsetEnabled] = useState(true);
  const [maxPatientsText, setMaxPatientsText] = useState("250");
  const [exportAgeMinText, setExportAgeMinText] = useState("");
  const [exportAgeMaxText, setExportAgeMaxText] = useState("");
  const [recordsPerPatientMinText, setRecordsPerPatientMinText] = useState("");
  const [recordsPerPatientMaxText, setRecordsPerPatientMaxText] = useState("");

  const defaultProfile = useMemo(() => profiles.find((p) => p.profile_name === "baseline_fam_scan") ?? profiles[0], [profiles]);
  const selectedProfile = useMemo(() => {
    if (profileName) return profiles.find((p) => p.profile_name === profileName) ?? defaultProfile;
    return defaultProfile;
  }, [profileName, profiles, defaultProfile]);

  useEffect(() => {
    if (!selectedProfile) return;
    setExtractRegex(selectedProfile.extract_regex ?? "Family History:\\n(.*?)\\n\\n");
    setTrimHeadersText((selectedProfile.trim_after_headers ?? ["Physical Exam:"]).join("\n"));
    setIcdPrefixesText(selectedProfile.icd_prefixes.join("\n"));
    const nextKeywordText: Record<string, string> = {};
    Object.entries(selectedProfile.keyword_groups).forEach(([group, terms]) => {
      nextKeywordText[group] = terms.join("\n");
    });
    setKeywordText(nextKeywordText);
    setCancerTypesText(Object.keys(selectedProfile.keyword_groups).join("\n"));
  }, [selectedProfile]);

  const keywordGroups = useMemo(() => Object.keys(keywordText), [keywordText]);

  const parsedOverrides: ConfigOverrides = {
    family_history: {
      extract_regex: extractRegex.trim(),
      trim_after_headers: trimHeadersText
        .split("\n")
        .map((x) => x.trim())
        .filter(Boolean),
    },
    structured_data: {
      icd_prefixes: icdPrefixesText
        .split("\n")
        .map((x) => x.trim())
        .filter(Boolean),
    },
    keywords: Object.fromEntries(
      keywordGroups.map((group) => [
        group,
        keywordText[group]
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
      ])
    ),
    cohort: {
      refiners: {
        enabled: refinersEnabled,
        genders: gendersText
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
        age_min: ageMinText.trim() === "" ? null : Number(ageMinText),
        age_max: ageMaxText.trim() === "" ? null : Number(ageMaxText),
        note_length_min: noteLengthMinText.trim() === "" ? null : Number(noteLengthMinText),
        note_length_max: noteLengthMaxText.trim() === "" ? null : Number(noteLengthMaxText),
        notes_per_patient_min:
          notesPerPatientMinText.trim() === "" ? null : Number(notesPerPatientMinText),
        notes_per_patient_max:
          notesPerPatientMaxText.trim() === "" ? null : Number(notesPerPatientMaxText),
        cancer_types: cancerTypesText
          .split("\n")
          .map((x) => x.trim().toLowerCase())
          .filter(Boolean),
      },
    },
    garde_export: { enabled: gardeExportEnabled },
    export_subset: gardeExportEnabled ? {
      enabled: exportSubsetEnabled,
      max_patients: maxPatientsText.trim() === "" ? 250 : Number(maxPatientsText),
      age_min: exportAgeMinText.trim() === "" ? null : Number(exportAgeMinText),
      age_max: exportAgeMaxText.trim() === "" ? null : Number(exportAgeMaxText),
      records_per_patient_min: recordsPerPatientMinText.trim() === "" ? null : Number(recordsPerPatientMinText),
      records_per_patient_max: recordsPerPatientMaxText.trim() === "" ? null : Number(recordsPerPatientMaxText),
    } : undefined,
    llm: llmModel.trim() ? { provider: llmProvider, model: llmModel.trim() } : undefined,
  };

  return (
    <section className="panel">
      <h2>Step 1: Create Run</h2>
      <p className="muted">
        Create a new run with a unique ID. Use defaults or pick a profile. Enable GARDE export to generate demographics and family history CSVs.
      </p>
      <div className="grid">
        <label>
          Run ID
          <input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="e.g. my_run_001" />
        </label>
        <label>
          Profile (optional)
          <select value={profileName} onChange={(e) => setProfileName(e.target.value)}>
            <option value="">Default (baseline)</option>
            {profiles.map((profile) => (
              <option key={profile.profile_name} value={profile.profile_name}>
                {profile.profile_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          GARDE export
          <select
            value={gardeExportEnabled ? "yes" : "no"}
            onChange={(e) => setGardeExportEnabled(e.target.value === "yes")}
          >
            <option value="yes">Yes (Stages 1–4, full pipeline)</option>
            <option value="no">No (Stages 1–3 only)</option>
          </select>
        </label>
      </div>
      <button
        className="primaryButton"
        disabled={busy || !runId.trim()}
        onClick={() =>
          onCreateRun({
            runId: runId.trim(),
            configPath: "config/pre_llm_config.json",
            profileName: profileName || undefined,
            configOverrides: parsedOverrides,
          })
        }
      >
        Create Run
      </button>

      <details className="customizeDetails" open={customizeOpen} onToggle={() => setCustomizeOpen((v) => !v)}>
        <summary>Customize (extraction, refiners, keywords, LLM)</summary>
        <div className="customizeContent">
          <h3>Extraction Rules</h3>
          <div className="grid">
            <label>
              Family History regex
              <input value={extractRegex} onChange={(e) => setExtractRegex(e.target.value)} />
            </label>
            <label>
              Trim after headers (one per line)
              <textarea rows={2} value={trimHeadersText} onChange={(e) => setTrimHeadersText(e.target.value)} />
            </label>
            <label>
              ICD prefixes (one per line)
              <textarea rows={2} value={icdPrefixesText} onChange={(e) => setIcdPrefixesText(e.target.value)} />
            </label>
          </div>

          <h3>Stage 2 Cohort Refiners</h3>
          <div className="grid">
            <label>
              Enable refiners
              <select value={refinersEnabled ? "yes" : "no"} onChange={(e) => setRefinersEnabled(e.target.value === "yes")}>
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </select>
            </label>
            <label>Genders (one per line)<textarea rows={2} value={gendersText} onChange={(e) => setGendersText(e.target.value)} /></label>
            <label>Age min<input value={ageMinText} onChange={(e) => setAgeMinText(e.target.value)} placeholder="e.g. 30" /></label>
            <label>Age max<input value={ageMaxText} onChange={(e) => setAgeMaxText(e.target.value)} placeholder="e.g. 75" /></label>
            <label>Note length min<input value={noteLengthMinText} onChange={(e) => setNoteLengthMinText(e.target.value)} /></label>
            <label>Note length max<input value={noteLengthMaxText} onChange={(e) => setNoteLengthMaxText(e.target.value)} /></label>
            <label>Notes/patient min<input value={notesPerPatientMinText} onChange={(e) => setNotesPerPatientMinText(e.target.value)} /></label>
            <label>Notes/patient max<input value={notesPerPatientMaxText} onChange={(e) => setNotesPerPatientMaxText(e.target.value)} /></label>
            <label>Cancer types (one per line)<textarea rows={2} value={cancerTypesText} onChange={(e) => setCancerTypesText(e.target.value)} /></label>
          </div>

          <h3>Export Subset (before Stage 4, reduces LLM cost)</h3>
          <div className="grid">
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

          <h3>Stage 4 LLM</h3>
          <div className="grid">
            <label>
              Provider
              <select value={llmProvider} onChange={(e) => setLlmProvider(e.target.value as "openai" | "azure")}>
                <option value="openai">OpenAI</option>
                <option value="azure">Azure</option>
              </select>
            </label>
            <label>
              Model / deployment
              <input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} placeholder={llmProvider === "azure" ? "deployment name" : "e.g. gpt-4"} />
            </label>
          </div>

          <h3>Cancer Keywords</h3>
          <div className="grid">
            {keywordGroups.map((group) => (
              <label key={group}>
                {group}
                <textarea rows={4} value={keywordText[group] ?? ""} onChange={(e) => setKeywordText({ ...keywordText, [group]: e.target.value })} />
              </label>
            ))}
          </div>
        </div>
      </details>
    </section>
  );
}
