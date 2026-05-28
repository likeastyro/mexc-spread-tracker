from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Any

from aiogram import Bot, Dispatcher

from bot.consumer import SpreadConsumer, SubscriberRegistry, TokenBlacklistRegistry
from bot.handlers import get_router


def build_dispatcher(
    *,
    subscribers: SubscriberRegistry,
    blacklist: TokenBlacklistRegistry,
    admin_ids: set[int],
) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(get_router(subscribers, blacklist, admin_ids))
    return dispatcher


async def run_bot(
    *,
    token: str,
    queue: asyncio.Queue[Any],
) -> None:
    bot = Bot(token=token)
    subscribers = SubscriberRegistry()
    blacklist = TokenBlacklistRegistry(db_path=_blacklist_db_path())
    admin_ids = _load_admin_ids()
    dispatcher = build_dispatcher(
        subscribers=subscribers,
        blacklist=blacklist,
        admin_ids=admin_ids,
    )
    consumer = SpreadConsumer(
        bot=bot,
        subscribers=subscribers,
        blacklist=blacklist,
        queue=queue,
    )

    consumer_task = asyncio.create_task(consumer.run())
    try:
        await dispatcher.start_polling(bot)
    finally:
        consumer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consumer_task
        await bot.session.close()


def _load_admin_ids() -> set[int]:
    admin_ids: set[int] = set()
    for key in ("ADMIN_ONE_ID", "ADMIN_TWO_ID"):
        value = os.getenv(key)
        if not value:
            continue
        try:
            admin_ids.add(int(value))
        except ValueError:
            continue
    return admin_ids


def _blacklist_db_path() -> str:
    return os.getenv("BLACKLIST_DB_PATH", ".bot_state/blacklist.sqlite3")
