"""Stage 4c: LLM imputation of ___ placeholders in family history text."""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from typing import Any, NamedTuple

import pandas as pd

logger = logging.getLogger(__name__)

# Match notebook / prompt: '__', '___', '____' (longest-first in alternation)
_PLACEHOLDER_RE = re.compile(r"____|___|__")

IMPUTATION_PROMPT = """You are an expert medical language model. Your task is to replace missing values marked as '___' or '__' or '____'
in the provided family history text. Use the patient's gender ({gender}) and age ({age}) for context.
Ensure the imputed values are medically realistic and align with the overall context. Please do
not include any additional comments or notes during this task.

Example Input:
"Father, aged ___, suffers from Diverticular Disease for ___ years."
Output:
"Father, aged 67, suffers from Diverticular Disease for 10 years."

Now process the following text:
{text}

Output:
"""


def count_placeholder_matches(text: str | None) -> int:
    """Count non-overlapping placeholder tokens (__, ___, ____) in text."""
    if not text:
        return 0
    return len(_PLACEHOLDER_RE.findall(str(text)))


def _format_age_for_prompt(age: Any) -> str:
    """Stable age string for the prompt; avoids int() on bad dtypes."""
    if age is None:
        return "unknown"
    try:
        if pd.isna(age):
            return "unknown"
    except TypeError:
        pass
    try:
        a = float(str(age).strip()) if isinstance(age, str) else float(age)
    except (TypeError, ValueError, OverflowError):
        return "unknown"
    if pd.isna(a) or a != a:  # NaN
        return "unknown"
    try:
        return str(int(round(a)))
    except (ValueError, OverflowError):
        return "unknown"


def _format_gender_for_prompt(gender: Any) -> str:
    if gender is None:
        return "unknown"
    try:
        if pd.isna(gender):
            return "unknown"
    except TypeError:
        pass
    return str(gender).strip() or "unknown"


def _model_uses_reasoning_completion_budget(model: str) -> bool:
    """gpt-5 / o-series consume much of max_completion_tokens before visible output."""
    m = (model or "").lower().strip()
    return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3")


def _effective_max_tokens(
    text: str,
    max_tokens_cap: int,
    model: str = "",
    min_floor: int = 800,
) -> int:
    """Scale completion budget with input length (~3 chars per token heuristic)."""
    if max_tokens_cap <= 0:
        return 800
    floor = 3072 if _model_uses_reasoning_completion_budget(model) else min_floor
    n = len(text or "")
    if n == 0:
        return min(max_tokens_cap, 512 if floor <= 800 else min(floor, max_tokens_cap))
    estimated = max(floor, n // 3 + 200)
    if _model_uses_reasoning_completion_budget(model):
        # Extra headroom: reasoning tokens often dominate the completion budget.
        estimated = max(estimated, (n // 3 + 200) * 3)
    return min(max_tokens_cap, estimated)


class ImputeOneResult(NamedTuple):
    text: str
    error: str | None
    finish_reason: str | None


def _get_openai_client(config: dict[str, Any]) -> Any:
    """Return OpenAI or Azure OpenAI client based on config."""
    try:
        import openai
    except ImportError:
        raise ImportError("openai package is required for LLM imputation. Install with: pip install openai")

    llm_cfg = config.get("llm", {})
    provider = (llm_cfg.get("provider") or "openai").lower().strip()
    model = llm_cfg.get("model") or ""

    if provider == "azure":
        api_key_env = llm_cfg.get("azure_api_key_env", "AZURE_OPENAI_API_KEY")
        endpoint_env = llm_cfg.get("azure_endpoint_env", "AZURE_OPENAI_ENDPOINT")
        api_key = os.environ.get(api_key_env)
        endpoint = os.environ.get(endpoint_env)
        if not api_key or not endpoint or not model:
            raise ValueError(
                f"Azure LLM requires {api_key_env}, {endpoint_env} env vars and llm.model (deployment name)"
            )
        return openai.AzureOpenAI(
            api_version=llm_cfg.get("azure_api_version", "2024-02-15-preview"),
            azure_endpoint=endpoint,
            api_key=api_key,
        ), model, "azure"
    else:
        api_key_env = llm_cfg.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(f"OpenAI LLM requires {api_key_env} env var")
        model = model or os.environ.get("OPENAI_MODEL", "")
        if not model:
            raise ValueError("OpenAI LLM requires llm.model in config or OPENAI_MODEL in .env")
        base_url = os.environ.get("OPENAI_BASE_URL") or llm_cfg.get("base_url")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return openai.OpenAI(**kwargs), model, "openai"


def _completion_budget_kwargs(model: str, n: int) -> dict[str, Any]:
    """
    OpenAI chat.completions: some models (e.g. gpt-5*) reject `max_tokens` and require
    `max_completion_tokens` instead.
    """
    m = (model or "").lower().strip()
    if m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3"):
        return {"max_completion_tokens": n}
    return {"max_tokens": n}


def _model_requires_default_temperature_only(model: str) -> bool:
    """
    Some models (e.g. gpt-5-mini) reject non-default temperature; API returns 400 for e.g. 0.7
    with: "Only the default (1) value is supported."
    """
    m = (model or "").lower().strip()
    return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3")


def _temperature_kwargs(model: str, temperature: float) -> dict[str, Any]:
    """Omit temperature when the model only allows the server default."""
    if _model_requires_default_temperature_only(model):
        return {}
    return {"temperature": temperature}


def _call_completion(
    client: Any,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
) -> ImputeOneResult:
    """Single chat.completions call; returns text + error + finish_reason."""
    budget = _completion_budget_kwargs(model, max_tokens)
    temp_kw = _temperature_kwargs(model, temperature)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **temp_kw,
            **budget,
        )
        choice = response.choices[0]
        fr = getattr(choice, "finish_reason", None)
        content = choice.message.content if choice.message else None
        if content is None:
            return ImputeOneResult(text="", error="empty_model_content", finish_reason=fr)
        return ImputeOneResult(text=content.strip(), error=None, finish_reason=fr)
    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        logger.warning("LLM imputation API call failed: %s", err_msg)
        return ImputeOneResult(text="", error=err_msg, finish_reason=None)


def _impute_one(
    client: Any,
    model: str,
    text: str,
    gender: Any,
    age: Any,
    temperature: float,
    max_tokens: int,
    max_tokens_absolute_cap: int,
) -> ImputeOneResult:
    """
    Impute placeholders; if finish_reason is 'length' (truncation), retry with larger
    completion budgets until stop or cap. gpt-5* often needs multiple steps: reasoning
    consumes max_completion_tokens before the visible answer.
    """
    gender_str = _format_gender_for_prompt(gender)
    age_str = _format_age_for_prompt(age)
    raw = text or ""
    # Inner braces in clinical text are literal once passed as `text=` to format.
    prompt = IMPUTATION_PROMPT.format(gender=gender_str, age=age_str, text=raw)

    cap = min(max_tokens, max_tokens_absolute_cap)
    effective = _effective_max_tokens(raw, cap, model=model)

    result = _call_completion(client, model, prompt, temperature, effective)
    if result.error:
        return ImputeOneResult(text=raw, error=result.error, finish_reason=result.finish_reason)

    best = result
    used_budget = effective

    while best.finish_reason == "length" and not best.error:
        next_budget = min(max_tokens_absolute_cap, max(used_budget * 2, used_budget + 1024))
        if next_budget <= used_budget:
            break
        logger.info(
            "LLM finish_reason=length; retrying with completion_budget=%s (was %s)",
            next_budget,
            used_budget,
        )
        retry = _call_completion(client, model, prompt, temperature, next_budget)
        if retry.error:
            return ImputeOneResult(
                text=best.text or raw,
                error=retry.error,
                finish_reason=best.finish_reason,
            )
        best = retry
        used_budget = next_budget

    out = best.text or raw
    return ImputeOneResult(text=out, error=None, finish_reason=best.finish_reason)


def run_llm_imputation(
    consolidated_df: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply LLM imputation to consolidated FH text. Returns (df with imputed_family_history, qc)."""
    llm_cfg = config.get("llm", {})
    temperature = float(llm_cfg.get("temperature", 0.7))
    max_tokens = int(llm_cfg.get("max_tokens", 2048))
    # Hard ceiling for scaling (OpenAI models often allow 4k–16k+ completion; stay conservative)
    max_tokens_absolute_cap = int(llm_cfg.get("max_tokens_cap", 8192))

    try:
        client, model, provider = _get_openai_client(config)
    except (ImportError, ValueError) as e:
        return consolidated_df.copy(), {
            "imputation_skipped": True,
            "imputation_reason": str(e),
            "imputed_count": 0,
            "raw_count": int(len(consolidated_df)),
        }

    df = consolidated_df.copy()
    imputed: list[str] = []
    api_error_count = 0
    finish_reason_counter: Counter[str] = Counter()
    placeholders_before_total = 0
    placeholders_after_total = 0
    rows_with_remaining_placeholders = 0
    rows_truncated = 0
    sample_error: str | None = None

    for _, row in df.iterrows():
        text = row.get("merged_family_history", "")
        gender = row.get("gender")
        age = row.get("anchor_age")
        pb = count_placeholder_matches(str(text) if text is not None else "")
        placeholders_before_total += pb

        one = _impute_one(
            client,
            model,
            str(text) if text is not None else "",
            gender,
            age,
            temperature,
            max_tokens,
            max_tokens_absolute_cap,
        )

        if one.error:
            api_error_count += 1
            if sample_error is None:
                sample_error = one.error[:500]
            fallback = one.text or (str(text) if text is not None else "")
            imputed.append(fallback)
            pa = count_placeholder_matches(fallback)
        else:
            out = one.text
            imputed.append(out)
            pa = count_placeholder_matches(out)
            if one.finish_reason:
                finish_reason_counter[one.finish_reason] += 1
                if one.finish_reason == "length":
                    rows_truncated += 1

        placeholders_after_total += pa
        if pa > 0:
            rows_with_remaining_placeholders += 1

    df["imputed_family_history"] = imputed

    n_rows = int(len(consolidated_df))
    api_success_count = n_rows - api_error_count
    imputation_partial = bool(
        api_error_count > 0 or rows_with_remaining_placeholders > 0 or rows_truncated > 0
    )

    qc: dict[str, Any] = {
        "imputation_skipped": False,
        "imputed_count": n_rows,
        "api_success_count": api_success_count,
        "api_error_count": api_error_count,
        "raw_count": n_rows,
        "provider": provider,
        "placeholders_total_before": placeholders_before_total,
        "placeholders_total_after": placeholders_after_total,
        "rows_with_remaining_placeholders": rows_with_remaining_placeholders,
        "rows_finish_reason_length": rows_truncated,
        "finish_reason_counts": dict(finish_reason_counter),
        "imputation_partial": imputation_partial,
    }
    if sample_error:
        qc["sample_error"] = sample_error

    return df, qc
