from __future__ import annotations

import os


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# WebSocket endpoints
SPOT_WS_URL = _env_str("SPOT_WS_URL", "wss://wbs-api.mexc.com/ws")
FUT_WS_URL = _env_str("FUT_WS_URL", "wss://contract.mexc.com/edge")

# Channels
SPOT_TICKERS_CHANNEL = _env_str(
    "SPOT_TICKERS_CHANNEL",
    "spot@public.miniTickers.v3.api.pb@UTC+8",
)
FUT_TICKERS_CHANNEL = _env_str("FUT_TICKERS_CHANNEL", "sub.tickers")

# Heartbeat & reconnect
PING_INTERVAL_SEC = _env_int("PING_INTERVAL_SEC", 15)
RECONNECT_DELAY_SEC = _env_int("RECONNECT_DELAY_SEC", 5)

# Liquidity filter
MIN_VOLUME_24H_USD = _env_float("MIN_VOLUME_24H_USD", 100_000)

# Symbol normalization
QUOTE = _env_str("QUOTE", "USDT")

# Spread lifecycle thresholds
OPEN_THRESHOLD = _env_float("OPEN_THRESHOLD", 1.5)
CLOSE_THRESHOLD = _env_float("CLOSE_THRESHOLD", 0.5)
DEEPEN_TRIGGER = _env_float("DEEPEN_TRIGGER", 1.5)

# Debounce settings
OPEN_DEBOUNCE = _env_int("OPEN_DEBOUNCE", 3)
CLOSE_DEBOUNCE = _env_int("CLOSE_DEBOUNCE", 5)
DEEPEN_DEBOUNCE = _env_int("DEEPEN_DEBOUNCE", 3)

# Persistence
SNAPSHOT_INTERVAL_SEC = _env_int("SNAPSHOT_INTERVAL_SEC", 60)
STATE_FILE_PATH = _env_str("STATE_FILE_PATH", "data/state.json")
