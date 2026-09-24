"""Script to execute full 2026 research pipeline, regimes, events, behavior map, and reports."""

from coin_behavior_engine.cli import cmd_research
from coin_behavior_engine.config.loader import load_config

if __name__ == "__main__":
    config = load_config()
    cmd_research(config)
