from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot

from bot.formatters import event_thread_key, format_event_message

logger = logging.getLogger(__name__)


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
        queue: asyncio.Queue[Any],
    ) -> None:
        self.bot = bot
        self.subscribers = subscribers
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
        event_reply_id = _message_id_from_event(event)
        if event_reply_id is not None:
            return event_reply_id
        if _event_type(event) in {"deepen", "close"}:
            return self._message_ids_by_chat.get(chat_id, {}).get(key)
        return None

    def _remember_message(
        self,
        chat_id: int,
        key: str,
        event_type: str,
        message_id: int,
    ) -> None:
        chat_messages = self._message_ids_by_chat.setdefault(chat_id, {})
        if event_type == "open":
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
    while True:
        now = datetime.now(timezone.utc)
        spread_id = f"BTC_USDT:{int(now.timestamp())}"
        events = [
            FakeSpreadEvent(
                event_type="open",
                spread_id=spread_id,
                symbol="PEPE",
                direction="LONG",
                spread_pct=10.77,
                daily_peak_pct=10.77,
                volume_24h_usd=4_200_000,
                spot_price=0.001200,
                fut_price=0.001329,
                timestamp=now,
            ),
            FakeSpreadEvent(
                event_type="deepen",
                spread_id=spread_id,
                symbol="PEPE",
                direction="LONG",
                spread_pct=14.20,
                daily_peak_pct=14.20,
                volume_24h_usd=4_200_000,
                duration_sec=38,
                spot_price=0.001210,
                fut_price=0.001382,
                timestamp=datetime.now(timezone.utc),
            ),
            FakeSpreadEvent(
                event_type="close",
                spread_id=spread_id,
                symbol="PEPE",
                direction="LONG",
                spread_pct=0.31,
                daily_peak_pct=14.20,
                duration_sec=94,
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
    consumer = SpreadConsumer(bot=bot, subscribers=subscribers, queue=queue)

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
