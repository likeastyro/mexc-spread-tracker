from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiogram import Bot

from bot.formatters import event_thread_key, format_event_message

logger = logging.getLogger(__name__)


class TokenBlacklistRegistry:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        self._symbols = self._load_symbols()

    def add(self, symbol: str) -> str:
        normalized = _normalize_symbol(symbol)
        self._symbols.add(normalized)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO banned_tokens(symbol) VALUES (?)",
                (normalized,),
            )
        return normalized

    def remove(self, symbol: str) -> str:
        normalized = _normalize_symbol(symbol)
        self._symbols.discard(normalized)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM banned_tokens WHERE symbol = ?",
                (normalized,),
            )
        return normalized

    def contains(self, symbol: str) -> bool:
        return _normalize_symbol(symbol) in self._symbols

    def list_symbols(self) -> tuple[str, ...]:
        return tuple(sorted(self._symbols))

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS banned_tokens (
                    symbol TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _load_symbols(self) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT symbol FROM banned_tokens ORDER BY symbol"
            ).fetchall()
        return {str(row[0]) for row in rows}

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)


class SubscriberRegistry:
    def __init__(self) -> None:
        self._chat_ids: set[int] = set()

    def add(self, chat_id: int) -> None:
        self._chat_ids.add(chat_id)

    def remove(self, chat_id: int) -> None:
        self._chat_ids.discard(chat_id)

    def list_chat_ids(self) -> tuple[int, ...]:
        return tuple(self._chat_ids)

    def is_empty(self) -> bool:
        return not self._chat_ids


class SpreadConsumer:
    def __init__(
        self,
        *,
        bot: Bot,
        subscribers: SubscriberRegistry,
        blacklist: TokenBlacklistRegistry,
        queue: asyncio.Queue[Any],
    ) -> None:
        self.bot = bot
        self.subscribers = subscribers
        self.blacklist = blacklist
        self.queue = queue
        self._message_ids_by_chat: dict[int, dict[str, int]] = {}

    async def run(self) -> None:
        while True:
            event = await self.queue.get()
            try:
                await self._handle_event(event)
            except Exception:
                logger.exception("Failed to process spread event: %r", event)
            finally:
                self.queue.task_done()

    async def _handle_event(self, event: Any) -> None:
        if self.subscribers.is_empty():
            logger.debug("Skipping spread event because there are no subscribers yet")
            return

        symbol = _symbol_from_event(event)
        if symbol and self.blacklist.contains(symbol):
            logger.debug("Skipping blacklisted token event: %s", symbol)
            return

        text, reply_markup = format_event_message(event)
        key = event_thread_key(event)
        event_type = _event_type(event)

        for chat_id in self.subscribers.list_chat_ids():
            reply_to_message_id = self._reply_to_message_id(chat_id, event, key)
            sent_message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                reply_to_message_id=reply_to_message_id,
            )
            self._remember_message(chat_id, key, event_type, sent_message.message_id)

    def _reply_to_message_id(self, chat_id: int, event: Any, key: str) -> int | None:
        if _event_type(event) in {"deepen", "close"}:
            remembered_message_id = self._message_ids_by_chat.get(chat_id, {}).get(key)
            if remembered_message_id is not None:
                return remembered_message_id
        event_reply_id = _message_id_from_event(event)
        if event_reply_id is not None:
            return event_reply_id
        return None

    def _remember_message(
        self,
        chat_id: int,
        key: str,
        event_type: str,
        message_id: int,
    ) -> None:
        chat_messages = self._message_ids_by_chat.setdefault(chat_id, {})
        if event_type in {"open", "deepen"}:
            chat_messages[key] = message_id
        elif event_type == "close":
            chat_messages.pop(key, None)


@dataclass(slots=True)
class FakeSpreadEvent:
    event_type: str
    spread_id: str
    symbol: str
    direction: str
    spread_pct: float
    daily_peak_pct: float | None = None
    volume_24h_usd: float | None = None
    duration_sec: int | None = None
    reply_to_message_id: int | None = None
    spot_price: float | None = None
    fut_price: float | None = None
    timestamp: datetime | None = None


async def fake_event_producer(
    queue: asyncio.Queue[Any],
    *,
    interval_seconds: float = 2.0,
    repeat: bool = False,
) -> None:
    daily_peaks: dict[tuple[str, str], float] = {}
    peak_day = datetime.now(timezone.utc).date()
    symbols = tuple(_FAKE_MARKET_PROFILES)

    while True:
        now = datetime.now(timezone.utc)
        current_day = now.date()
        if current_day != peak_day:
            daily_peaks.clear()
            peak_day = current_day

        symbol = random.choice(symbols)
        direction = random.choice(("LONG", "SHORT"))
        sign = 1 if direction == "LONG" else -1
        profile = _FAKE_MARKET_PROFILES[symbol]
        spread_id = f"{symbol}_USDT:{int(now.timestamp())}"

        spot_price = _fake_spot_price(symbol)
        open_spread_abs = round(
            random.uniform(profile["open_min"], profile["open_max"]),
            2,
        )
        deepen_target_abs = round(
            random.uniform(open_spread_abs, profile["peak_cap"]),
            2,
        )

        peak_key = (symbol, direction)
        current_peak = daily_peaks.get(peak_key, 0.0)
        open_peak_abs = max(current_peak, open_spread_abs)
        daily_peaks[peak_key] = max(open_peak_abs, deepen_target_abs)
        deepen_peak_abs = daily_peaks[peak_key]
        deepen_spread_abs = deepen_peak_abs

        open_fut_price = _apply_spread_to_price(spot_price, sign * open_spread_abs)
        deepen_spot_price = _jitter_price(spot_price)
        deepen_fut_price = _apply_spread_to_price(deepen_spot_price, sign * deepen_spread_abs)

        volume_24h_usd = round(random.uniform(150_000, 95_000_000), 2)
        open_spread = sign * open_spread_abs
        deepen_spread = sign * deepen_spread_abs

        events = [
            FakeSpreadEvent(
                event_type="open",
                spread_id=spread_id,
                symbol=symbol,
                direction=direction,
                spread_pct=open_spread,
                daily_peak_pct=open_peak_abs,
                volume_24h_usd=volume_24h_usd,
                spot_price=spot_price,
                fut_price=open_fut_price,
                timestamp=now,
            ),
            FakeSpreadEvent(
                event_type="deepen",
                spread_id=spread_id,
                symbol=symbol,
                direction=direction,
                spread_pct=deepen_spread,
                daily_peak_pct=deepen_peak_abs,
                volume_24h_usd=volume_24h_usd,
                duration_sec=random.randint(15, 1800),
                spot_price=deepen_spot_price,
                fut_price=deepen_fut_price,
                timestamp=datetime.now(timezone.utc),
            ),
            FakeSpreadEvent(
                event_type="close",
                spread_id=spread_id,
                symbol=symbol,
                direction=direction,
                spread_pct=round(sign * random.uniform(0.05, 0.95), 2),
                daily_peak_pct=deepen_peak_abs,
                duration_sec=random.randint(30, 7200),
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        for event in events:
            await queue.put(event)
            await asyncio.sleep(interval_seconds)

        if not repeat:
            return


async def run_fake_consumer(
    *,
    bot: Bot,
    chat_id: int,
    interval_seconds: float = 2.0,
) -> None:
    queue: asyncio.Queue[Any] = asyncio.Queue()
    subscribers = SubscriberRegistry()
    subscribers.add(chat_id)
    blacklist = TokenBlacklistRegistry(db_path=".bot_state/blacklist.sqlite3")
    consumer = SpreadConsumer(
        bot=bot,
        subscribers=subscribers,
        blacklist=blacklist,
        queue=queue,
    )

    producer_task = asyncio.create_task(
        fake_event_producer(queue, interval_seconds=interval_seconds, repeat=True)
    )
    consumer_task = asyncio.create_task(consumer.run())

    try:
        await asyncio.gather(producer_task, consumer_task)
    finally:
        producer_task.cancel()
        consumer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await producer_task
        with contextlib.suppress(asyncio.CancelledError):
            await consumer_task


def _event_type(event: Any) -> str:
    value = getattr(event, "event_type", None)
    if value is None and isinstance(event, dict):
        value = event.get("event_type") or event.get("type") or event.get("action")

    normalized = str(value or "open").strip().lower()
    if normalized in {"deepen", "deepen_spread", "update"}:
        return "deepen"
    if normalized in {"close", "closed", "close_spread"}:
        return "close"
    return "open"


def _message_id_from_event(event: Any) -> int | None:
    value = getattr(event, "reply_to_message_id", None)
    if value is None and isinstance(event, dict):
        value = event.get("reply_to_message_id")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _symbol_from_event(event: Any) -> str | None:
    value = getattr(event, "symbol", None)
    if value is None and isinstance(event, dict):
        value = event.get("symbol")
    if value is None:
        return None
    return _normalize_symbol(str(value))


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().removesuffix("_USDT").removeprefix("#")


def _fake_spot_price(symbol: str) -> float:
    profile = _FAKE_MARKET_PROFILES.get(symbol, _DEFAULT_FAKE_PROFILE)
    low, high = profile["spot_range"]
    return round(random.uniform(low, high), 8)


def _jitter_price(price: float) -> float:
    shift = random.uniform(-0.03, 0.03)
    return round(price * (1 + shift), 8)


def _apply_spread_to_price(spot_price: float, spread_pct: float) -> float:
    return round(spot_price * (1 + spread_pct / 100), 8)


_DEFAULT_FAKE_PROFILE = {
    "spot_range": (0.01, 10.0),
    "open_min": 1.0,
    "open_max": 8.0,
    "peak_cap": 12.0,
}

_FAKE_MARKET_PROFILES: dict[str, dict[str, float | tuple[float, float]]] = {
    "PEPE": {
        "spot_range": (0.0000008, 0.003),
        "open_min": 4.0,
        "open_max": 14.0,
        "peak_cap": 22.0,
    },
    "LFI": {
        "spot_range": (0.05, 4.0),
        "open_min": 2.0,
        "open_max": 10.0,
        "peak_cap": 18.0,
    },
    "DOGE": {
        "spot_range": (0.05, 0.5),
        "open_min": 1.0,
        "open_max": 6.0,
        "peak_cap": 10.0,
    },
    "XRP": {
        "spot_range": (0.2, 3.5),
        "open_min": 1.0,
        "open_max": 12.0,
        "peak_cap": 34.0,
    },
    "WIF": {
        "spot_range": (0.1, 5.0),
        "open_min": 2.0,
        "open_max": 15.0,
        "peak_cap": 28.0,
    },
    "BONK": {
        "spot_range": (0.000001, 0.00008),
        "open_min": 3.0,
        "open_max": 18.0,
        "peak_cap": 32.0,
    },
}
