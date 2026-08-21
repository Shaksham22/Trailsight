"""Environment-backed configuration for the deterministic backend only."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from trailsight.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    database_path: Path
    static_directory: Path


def load_runtime_config(
    environment: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    """Load the approved deterministic runtime configuration."""

    values = os.environ if environment is None else environment
    raw_database_path = values.get("TRAILSIGHT_DB_PATH", "").strip()
    if not raw_database_path:
        raise ConfigurationError(
            "TRAILSIGHT_DB_PATH is required to start the Trailsight backend"
        )

    raw_static_directory = values.get(
        "TRAILSIGHT_STATIC_DIR", "frontend/dist"
    ).strip()
    if not raw_static_directory:
        raw_static_directory = "frontend/dist"

    return RuntimeConfig(
        database_path=Path(raw_database_path).expanduser(),
        static_directory=Path(raw_static_directory).expanduser(),
    )


def load_static_directory(environment: Mapping[str, str] | None = None) -> Path:
    """Load only the optional static integration path for ``create_app``."""

    values = os.environ if environment is None else environment
    raw_static_directory = values.get(
        "TRAILSIGHT_STATIC_DIR", "frontend/dist"
    ).strip()
    return Path(raw_static_directory or "frontend/dist").expanduser()
