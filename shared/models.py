from dataclasses import dataclass
from typing import Literal


@dataclass
class SpreadEvent:
    event_type: Literal["open", "deepen", "close"]
    symbol: str
    direction: Literal["LONG", "SHORT"]
    spot_price: float
    fut_price: float
    spread_pct: float
    daily_peak_pct: float
    volume_24h_usd: float
    spot_volume_24h_usd: float
    fut_volume_24h_usd: float
    duration_sec: int | None
    reply_to_message_id: int | None


@dataclass
class Ticker:
    market: Literal["spot", "futures"]
    symbol: str
    price: float
    volume_24h_usd: float
    timestamp: float
