"""Configuration loading, validation, and persistence for datagen (DR-03, TEST-GEN-001).

Owner: Data + ML Engineer
Charter: Pure numeric core, datagen/**, model artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from datagen.config.provenance import (
    UntaggedParameterError,
    enforce_provenance_tags,
)
from datagen.config.schema import DatagenConfig


def get_default_config() -> DatagenConfig:
    """Return the canonical, fully tagged default generator configuration."""
    return DatagenConfig()


def load_config(source: str | Path | dict[str, Any] | None = None) -> DatagenConfig:
    """Load and strictly validate a generator configuration.

    Enforces that every parameter carries a valid provenance tag ('cited', 'derived', 'assumed').
    Untagged parameters abort with UntaggedParameterError (TEST-GEN-001).

    Args:
        source: A file path (YAML/JSON), raw string, config dictionary, or None (for defaults).

    Returns:
        DatagenConfig: The validated configuration object.

    Raises:
        UntaggedParameterError: If any generator parameter lacks provenance metadata.
        InvalidProvenanceError: If provenance tag or metadata is invalid.
        ValidationError: If schema validation fails.
        FileNotFoundError: If source path does not exist.
    """
    if source is None:
        return get_default_config()

    data: dict[str, Any]
    if isinstance(source, dict):
        data = source
    elif isinstance(source, (str, Path)):
        source_path = Path(source)
        if source_path.is_file():
            raw_text = source_path.read_text(encoding="utf-8")
            if source_path.suffix.lower() == ".json":
                data = json.loads(raw_text)
            else:
                data = yaml.safe_load(raw_text)
        else:
            # Try parsing as inline YAML / JSON string
            raw_str = str(source)
            if raw_str.strip().startswith("{"):
                data = json.loads(raw_str)
            else:
                data = yaml.safe_load(raw_str)
    else:
        raise TypeError(f"Unsupported config source type: {type(source)}")

    if not isinstance(data, dict):
        raise ValueError(f"Config data must be a mapping, got {type(data)}")

    # 1. First-pass provenance enforcement: abort on any bare numeric literal in parameter sections
    enforce_provenance_tags(data)

    # 2. Pydantic schema validation
    try:
        config = DatagenConfig.model_validate(data)
    except ValidationError as err:
        # Check if error is due to an untagged parameter that was passed as an invalid type
        for error in err.errors():
            loc = ".".join(str(p) for p in error["loc"])
            msg = error["msg"]
            if "TaggedParameter" in msg or error["type"] in ("model_type", "missing"):
                if any(
                    section in loc
                    for section in (
                        "physics",
                        "class_mixture",
                        "process",
                        "degradation",
                        "factors",
                        "temperature",
                        "setup_effects",
                        "imperfections",
                    )
                ):
                    raise UntaggedParameterError(
                        f"Parameter '{loc}' fails provenance validation: {msg}. "
                        "Every generator parameter must carry cited|derived|assumed "
                        "per TEST-GEN-001."
                    ) from err
        raise

    return config


def save_config(config: DatagenConfig, path: str | Path) -> None:
    """Serialize and save configuration to YAML or JSON."""
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    raw_dict = config.model_dump(mode="json")

    if target_path.suffix.lower() == ".json":
        target_path.write_text(json.dumps(raw_dict, indent=2), encoding="utf-8")
    else:
        target_path.write_text(
            yaml.dump(raw_dict, sort_keys=False, default_flow_style=False), encoding="utf-8"
        )
