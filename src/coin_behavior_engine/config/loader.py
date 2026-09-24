"""Config loader parsing research.yaml into ResearchConfig."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union
import yaml

from coin_behavior_engine.config.schema import ResearchConfig
from coin_behavior_engine.utils.logging import logger

DEFAULT_CONFIG_PATH = Path("config/research.yaml")


def load_config(config_path: Optional[Union[str, Path]] = None) -> ResearchConfig:
    """Load configuration from YAML file or return defaults if not found."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        logger.warning(f"Config file not found at {path}. Using default configuration.")
        return ResearchConfig()

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    config = ResearchConfig.model_validate(data)
    logger.debug(f"Loaded configuration from {path}")
    return config
