"""Script to normalize raw data and validate data quality."""

from coin_behavior_engine.cli import cmd_validate
from coin_behavior_engine.config.loader import load_config

if __name__ == "__main__":
    config = load_config()
    cmd_validate(config)
