from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from aiogram import Bot, Dispatcher

from bot.consumer import SpreadConsumer, SubscriberRegistry
from bot.handlers import get_router


def build_dispatcher(*, subscribers: SubscriberRegistry) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(get_router(subscribers))
    return dispatcher


async def run_bot(
    *,
    token: str,
    queue: asyncio.Queue[Any],
) -> None:
    bot = Bot(token=token)
    subscribers = SubscriberRegistry()
    dispatcher = build_dispatcher(subscribers=subscribers)
    consumer = SpreadConsumer(bot=bot, subscribers=subscribers, queue=queue)

    consumer_task = asyncio.create_task(consumer.run())
    try:
        await dispatcher.start_polling(bot)
    finally:
        consumer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consumer_task
        await bot.session.close()
