# parser/config.py

# WebSocket endpoints
SPOT_WS_URL = "wss://wbs-api.mexc.com/ws"
FUT_WS_URL = "wss://contract.mexc.com/edge"

# Channels
SPOT_TICKERS_CHANNEL = "spot@public.miniTickers.v3.api.pb@UTC+8"
FUT_TICKERS_CHANNEL = "sub.tickers"

# Heartbeat & reconnect
PING_INTERVAL_SEC = 15
RECONNECT_DELAY_SEC = 5

# Filters
MIN_VOLUME_24H_USD = 100_000

# Symbol normalization
QUOTE = "USDT"

# State manager thresholds
OPEN_THRESHOLD = 1.5      # % — открыть алерт когда |спред| >= этого
CLOSE_THRESHOLD = 0.5     # % — закрыть алерт когда |спред| < этого
DEEPEN_TRIGGER = 1.5      # множитель — углубить когда |спред| >= peak * этого