"""Script to download historical BTCUSDT 5m candles from Binance."""

from coin_behavior_engine.cli import cmd_download
from coin_behavior_engine.config.loader import load_config

if __name__ == "__main__":
    config = load_config()
    cmd_download(config)
