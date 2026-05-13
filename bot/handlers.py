from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.consumer import SubscriberRegistry


def get_router(subscribers: SubscriberRegistry) -> Router:
    router = Router(name="spread-bot")

    @router.message(Command("start"))
    async def start_handler(message: Message) -> None:
        subscribers.add(message.chat.id)
        await message.answer(
            "MEXC spread bot is running.\n"
            "You are subscribed now. I will send alerts here when a spread opens, deepens, or aligns back."
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await message.answer(
            "Commands:\n"
            "/start - subscribe this chat\n"
            "/stop - unsubscribe this chat\n"
            "/help - show this message"
        )

    @router.message(Command("stop"))
    async def stop_handler(message: Message) -> None:
        subscribers.remove(message.chat.id)
        await message.answer("This chat is unsubscribed. Send /start to subscribe again.")

    return router
