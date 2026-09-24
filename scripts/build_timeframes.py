"""Script to aggregate canonical 5m candles into 15m, 1h, 4h, 1d."""

from coin_behavior_engine.cli import cmd_build
from coin_behavior_engine.config.loader import load_config

if __name__ == "__main__":
    config = load_config()
    cmd_build(config)
