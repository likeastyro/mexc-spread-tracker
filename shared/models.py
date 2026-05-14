from dataclasses import dataclass
from typing import Literal

@dataclass
class SpreadEvent:
    event_type: Literal["open", "deepen", "close"]
    symbol: str                          # "PEPE", без _USDT
    direction: Literal["LONG", "SHORT"]
    spot_price: float
    fut_price: float
    spread_pct: float                    # подписанный: LONG=+, SHORT=-
    daily_peak_pct: float                # |max| за сегодня UTC, для close
    volume_24h_usd: float
    duration_sec: int | None             # None для open
    reply_to_message_id: int | None      # None для open