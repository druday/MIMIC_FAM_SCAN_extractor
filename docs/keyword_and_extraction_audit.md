# Keyword and Extraction Audit (Strict Pipeline)

This note records the current strict extraction and keyword assumptions.

## Extraction Boundary Rules

- Family-history extraction regex: `Family History:\n(.*?)\n\n`
- Post-extraction trim headers: `Physical Exam:`
- Behavior is case-sensitive for section anchor and case-insensitive for keyword matching.

## Keyword Logic

- Matching is substring-based and case-insensitive.
- Category lists are configured in `config/pre_llm_config.json`:
  - `keywords.breast`
  - `keywords.ovarian`
  - `keywords.colorectal`
- Cross-category overlaps are expected for hereditary genes/syndromes (for example `BRCA1`, `BRCA2`, `Lynch syndrome` family terms).

## Accepted Strict Assumptions

- A note enters strict cohort candidacy only if it has:
  1. Extractable family-history text, and
  2. At least one configured cancer keyword hit.
- Validation linkage is resolved using deterministic ID priority:
  - `id` -> `note_id` -> `subject_id`.

## Deferred Enhancements (not applied yet)

- Regex variants for alternate section headers (for example `Family Hx:`).
- Word-boundary matching to reduce substring false positives.
- Synonym expansion with controlled vocabulary/ontology support.

