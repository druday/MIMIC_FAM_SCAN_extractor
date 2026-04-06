"""Configuration loading utilities for the pre-LLM pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(config_path: Path) -> dict[str, Any]:
    """Load JSON configuration and return a dictionary."""
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

