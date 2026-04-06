"""Tests for Stage 4c LLM imputation (mocked OpenAI client)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from mimic_repro.stages.llm_imputation import (
    _completion_budget_kwargs,
    _effective_max_tokens,
    _format_age_for_prompt,
    _temperature_kwargs,
    count_placeholder_matches,
    run_llm_imputation,
)


def test_count_placeholder_matches():
    assert count_placeholder_matches("a __ b ___ c ____ d") >= 3
    assert count_placeholder_matches("") == 0
    assert count_placeholder_matches("no placeholders") == 0


def test_format_age_for_prompt():
    assert _format_age_for_prompt(55.0) == "55"
    assert _format_age_for_prompt("62.5") == "62"
    assert _format_age_for_prompt(None) == "unknown"
    assert _format_age_for_prompt(float("nan")) == "unknown"


def test_completion_budget_kwargs_gpt4_vs_gpt5():
    assert _completion_budget_kwargs("gpt-4o-mini", 512) == {"max_tokens": 512}
    assert _completion_budget_kwargs("gpt-5-mini", 512) == {"max_completion_tokens": 512}


def test_temperature_kwargs_gpt5_omits_custom_temperature():
    assert _temperature_kwargs("gpt-5-mini", 0.7) == {}
    assert _temperature_kwargs("gpt-4o-mini", 0.7) == {"temperature": 0.7}


def test_effective_max_tokens_gpt5_uses_higher_floor():
    short = "Father: ___ cancer " * 5  # ~120 chars, many placeholders
    g5 = _effective_max_tokens(short, 8192, model="gpt-5-mini")
    g4 = _effective_max_tokens(short, 8192, model="gpt-4o-mini")
    assert g5 >= 3072
    assert g4 < g5


def _mock_response(content: str | None, finish_reason: str | None) -> MagicMock:
    r = MagicMock()
    ch = MagicMock()
    ch.message = MagicMock()
    ch.message.content = content
    ch.finish_reason = finish_reason
    r.choices = [ch]
    return r


@patch("mimic_repro.stages.llm_imputation._get_openai_client")
def test_run_llm_imputation_success_replaces_placeholders(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = (client, "gpt-4o-mini", "openai")
    client.chat.completions.create.return_value = _mock_response(
        "Father, aged 67, suffers from Diverticular Disease for 10 years.", "stop"
    )

    df = pd.DataFrame(
        {
            "merged_family_history": [
                "Father, aged ___, suffers from Diverticular Disease for ___ years."
            ],
            "gender": ["M"],
            "anchor_age": [70.0],
        }
    )
    cfg = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "max_tokens": 2048,
            "max_tokens_cap": 8192,
        }
    }

    out_df, qc = run_llm_imputation(df, cfg)

    assert qc["imputation_skipped"] is False
    assert qc["api_error_count"] == 0
    assert qc["api_success_count"] == 1
    assert qc["placeholders_total_before"] > 0
    assert qc["placeholders_total_after"] == 0
    assert qc["rows_with_remaining_placeholders"] == 0
    assert qc["imputation_partial"] is False
    assert "67" in out_df["imputed_family_history"].iloc[0]


@patch("mimic_repro.stages.llm_imputation._get_openai_client")
def test_run_llm_imputation_api_error_increments_error_count(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = (client, "gpt-4o-mini", "openai")
    client.chat.completions.create.side_effect = RuntimeError("rate limited")

    df = pd.DataFrame(
        {
            "merged_family_history": ["text with ___"],
            "gender": ["F"],
            "anchor_age": [40],
        }
    )
    cfg = {"llm": {"provider": "openai", "model": "gpt-4o-mini"}}

    out_df, qc = run_llm_imputation(df, cfg)

    assert qc["api_error_count"] == 1
    assert qc["api_success_count"] == 0
    assert qc["imputation_partial"] is True
    assert "sample_error" in qc
    assert out_df["imputed_family_history"].iloc[0] == "text with ___"


@patch("mimic_repro.stages.llm_imputation._get_openai_client")
def test_run_llm_imputation_truncation_then_retry(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = (client, "gpt-4o-mini", "openai")
    # First call: truncated; second: complete
    client.chat.completions.create.side_effect = [
        _mock_response("partial ___ tail", "length"),
        _mock_response("Father aged 67 no more ___", "stop"),
    ]

    df = pd.DataFrame(
        {
            "merged_family_history": ["Father aged ___ " * 50],
            "gender": ["M"],
            "anchor_age": [55],
        }
    )
    cfg = {"llm": {"provider": "openai", "model": "gpt-4o-mini", "max_tokens": 2048, "max_tokens_cap": 8192}}

    _out_df, qc = run_llm_imputation(df, cfg)

    assert client.chat.completions.create.call_count == 2
    assert qc["api_error_count"] == 0


@patch("mimic_repro.stages.llm_imputation._get_openai_client")
def test_run_llm_imputation_truncation_chains_retries(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = (client, "gpt-4o-mini", "openai")
    client.chat.completions.create.side_effect = [
        _mock_response("partial ___ tail", "length"),
        _mock_response("still ___ more", "length"),
        _mock_response("Father aged 67 no more placeholders", "stop"),
    ]

    df = pd.DataFrame(
        {
            "merged_family_history": ["Father aged ___ " * 50],
            "gender": ["M"],
            "anchor_age": [55],
        }
    )
    cfg = {"llm": {"provider": "openai", "model": "gpt-4o-mini", "max_tokens": 2048, "max_tokens_cap": 8192}}

    _out_df, qc = run_llm_imputation(df, cfg)

    assert client.chat.completions.create.call_count == 3
    assert qc["api_error_count"] == 0


@patch("mimic_repro.stages.llm_imputation._get_openai_client")
def test_gpt5_mini_uses_max_completion_tokens(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = (client, "gpt-5-mini", "openai")
    client.chat.completions.create.return_value = _mock_response(
        "Father, aged 67, suffers from Diverticular Disease for 10 years.", "stop"
    )

    df = pd.DataFrame(
        {
            "merged_family_history": [
                "Father, aged ___, suffers from Diverticular Disease for ___ years."
            ],
            "gender": ["M"],
            "anchor_age": [70.0],
        }
    )
    cfg = {
        "llm": {
            "provider": "openai",
            "model": "gpt-5-mini",
            "max_tokens": 2048,
            "max_tokens_cap": 8192,
        }
    }

    run_llm_imputation(df, cfg)

    kw = client.chat.completions.create.call_args.kwargs
    assert "max_completion_tokens" in kw
    assert kw["max_completion_tokens"] >= 1
    assert "max_tokens" not in kw
    assert "temperature" not in kw


def test_run_llm_imputation_skipped_no_client():
    df = pd.DataFrame({"merged_family_history": ["x"], "gender": ["F"], "anchor_age": [30]})
    with patch.dict("os.environ", {}, clear=False):
        # Ensure no key if present in env - patch OPENAI_API_KEY empty
        import os

        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            _, qc = run_llm_imputation(df, {"llm": {"provider": "openai", "model": "gpt-4o-mini"}})
            assert qc["imputation_skipped"] is True
            assert qc["imputed_count"] == 0
        finally:
            if old is not None:
                os.environ["OPENAI_API_KEY"] = old
