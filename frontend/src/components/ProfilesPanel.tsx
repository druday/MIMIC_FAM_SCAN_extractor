import { useState } from "react";

import type { Profile } from "../types";

type Props = {
  profiles: Profile[];
  onCreateProfile: (profile: Profile) => void;
  busy: boolean;
};

const DEFAULT_PROFILE: Profile = {
  profile_name: "",
  keyword_groups: { breast: [], ovarian: [], colorectal: [] },
  icd_prefixes: [],
};

export function ProfilesPanel({ profiles, onCreateProfile, busy }: Props) {
  const [draft, setDraft] = useState<Profile>(DEFAULT_PROFILE);

  return (
    <section className="panel">
      <h2>Replication Templates (Cancer Profiles)</h2>
      <p className="muted">
        Clone baseline logic for other cancers by defining keyword groups and ICD prefixes.
      </p>
      <div className="stageCard">
        <div>
          <label>
            Profile name
            <input
              value={draft.profile_name}
              onChange={(e) => setDraft({ ...draft, profile_name: e.target.value })}
            />
          </label>
          <label>
            ICD prefixes (comma-separated)
            <input
              value={draft.icd_prefixes.join(",")}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  icd_prefixes: e.target.value
                    .split(",")
                    .map((x) => x.trim())
                    .filter(Boolean),
                })
              }
            />
          </label>
        </div>
        <button
          disabled={busy || !draft.profile_name.trim()}
          onClick={() => onCreateProfile(draft)}
        >
          Save Profile
        </button>
      </div>
      <h3>Existing Profiles</h3>
      <ul>
        {profiles.map((profile) => (
          <li key={profile.profile_name}>
            <strong>{profile.profile_name}</strong> - ICD {profile.icd_prefixes.join(", ")} - groups{" "}
            {Object.keys(profile.keyword_groups).join(", ")}
          </li>
        ))}
      </ul>
    </section>
  );
}

