from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from bot.consumer import SubscriberRegistry, TokenBlacklistRegistry
from bot.keyboards import (
    about_panel_keyboard,
    admin_panel_keyboard,
    help_panel_keyboard,
)


def get_router(
    subscribers: SubscriberRegistry,
    blacklist: TokenBlacklistRegistry,
    admin_ids: set[int],
) -> Router:
    router = Router(name="spread-bot")
    started_at = datetime.now(timezone.utc)

    @router.message(Command("start"))
    async def start_handler(message: Message) -> None:
        subscribers.add(message.chat.id)
        await message.answer(
            "<b>MEXC Spread Bot</b>\n"
            "This chat is subscribed and ready.\n"
            "You will receive spread alerts here as soon as the parser detects open, deepen, and align events.",
            parse_mode="HTML",
            reply_markup=help_panel_keyboard(is_admin=_is_admin(message, admin_ids)),
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await message.answer(
            _help_text(is_admin=_is_admin(message, admin_ids)),
            parse_mode="HTML",
            reply_markup=help_panel_keyboard(is_admin=_is_admin(message, admin_ids)),
        )

    @router.message(Command("about"))
    async def about_handler(message: Message) -> None:
        await message.answer(
            _about_text(),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=about_panel_keyboard(is_admin=_is_admin(message, admin_ids)),
        )

    @router.message(Command("stop"))
    async def stop_handler(message: Message) -> None:
        subscribers.remove(message.chat.id)
        await message.answer(
            "This chat is unsubscribed.\n"
            "Send /start when you want to receive alerts again."
        )

    @router.message(Command("admin"))
    async def admin_handler(message: Message) -> None:
        if not _is_admin(message, admin_ids):
            await message.answer("Access denied.")
            return

        await message.answer(
            _admin_text(
                subscribers=subscribers,
                blacklist=blacklist,
                admin_ids=admin_ids,
                started_at=started_at,
            ),
            parse_mode="HTML",
            reply_markup=admin_panel_keyboard(),
        )

    @router.message(Command("ban_token"))
    async def ban_token_handler(message: Message, command: CommandObject) -> None:
        if not _is_admin(message, admin_ids):
            await message.answer("Access denied.")
            return

        symbol = (command.args or "").strip()
        if not symbol:
            await message.answer(
                "Usage: <code>/ban_token SYMBOL</code>\n"
                "Example: <code>/ban_token PEPE</code>",
                parse_mode="HTML",
            )
            return

        normalized = blacklist.add(symbol)
        await message.answer(
            f"Token <code>{normalized}</code> added to blacklist.\n"
            "New alerts for this symbol will be ignored.",
            parse_mode="HTML",
        )

    @router.message(Command("unban_token"))
    async def unban_token_handler(message: Message, command: CommandObject) -> None:
        if not _is_admin(message, admin_ids):
            await message.answer("Access denied.")
            return

        symbol = (command.args or "").strip()
        if not symbol:
            await message.answer(
                "Usage: <code>/unban_token SYMBOL</code>\n"
                "Example: <code>/unban_token PEPE</code>",
                parse_mode="HTML",
            )
            return

        normalized = blacklist.remove(symbol)
        await message.answer(
            f"Token <code>{normalized}</code> removed from blacklist.\n"
            "Alerts for this symbol are enabled again.",
            parse_mode="HTML",
        )

    @router.message(Command("banned_tokens"))
    async def banned_tokens_handler(message: Message) -> None:
        if not _is_admin(message, admin_ids):
            await message.answer("Access denied.")
            return

        symbols = blacklist.list_symbols()
        if not symbols:
            await message.answer("Blacklist is empty.")
            return

        await message.answer(
            "<b>Blacklisted Tokens</b>\n" + "\n".join(f"• <code>{symbol}</code>" for symbol in symbols),
            parse_mode="HTML",
        )

    @router.callback_query(F.data == "panel:help")
    async def help_panel_callback(callback: CallbackQuery) -> None:
        await _safe_edit_text(
            callback,
            text=_help_text(is_admin=_is_admin_callback(callback, admin_ids)),
            reply_markup=help_panel_keyboard(is_admin=_is_admin_callback(callback, admin_ids)),
        )
        await callback.answer()

    @router.callback_query(F.data == "panel:about")
    async def about_panel_callback(callback: CallbackQuery) -> None:
        await _safe_edit_text(
            callback,
            text=_about_text(),
            reply_markup=about_panel_keyboard(is_admin=_is_admin_callback(callback, admin_ids)),
        )
        await callback.answer()

    @router.callback_query(F.data == "panel:admin")
    async def admin_panel_callback(callback: CallbackQuery) -> None:
        if not _is_admin_callback(callback, admin_ids):
            await callback.answer("Access denied.", show_alert=True)
            return
        await _safe_edit_text(
            callback,
            text=_admin_text(
                subscribers=subscribers,
                blacklist=blacklist,
                admin_ids=admin_ids,
                started_at=started_at,
            ),
            reply_markup=admin_panel_keyboard(),
        )
        await callback.answer("Panel refreshed.")

    @router.callback_query(F.data == "panel:blacklist")
    async def blacklist_panel_callback(callback: CallbackQuery) -> None:
        if not _is_admin_callback(callback, admin_ids):
            await callback.answer("Access denied.", show_alert=True)
            return

        symbols = blacklist.list_symbols()
        body = "\n".join(f"• <code>{symbol}</code>" for symbol in symbols) if symbols else "No banned tokens yet."
        await _safe_edit_text(
            callback,
            text=(
                "<b>Blacklist</b>\n"
                "These symbols are blocked from sending alerts.\n\n"
                f"{body}\n\n"
                "Use <code>/ban_token SYMBOL</code> or <code>/unban_token SYMBOL</code> to manage it."
            ),
            reply_markup=admin_panel_keyboard(),
        )
        await callback.answer()

    return router


def _is_admin(message: Message, admin_ids: set[int]) -> bool:
    user = message.from_user
    return bool(user and user.id in admin_ids)


def _is_admin_callback(callback: CallbackQuery, admin_ids: set[int]) -> bool:
    user = callback.from_user
    return bool(user and user.id in admin_ids)


async def _safe_edit_text(
    callback: CallbackQuery,
    *,
    text: str,
    reply_markup,
) -> None:
    if callback.message is None:
        return
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=reply_markup,
    )


def _help_text(*, is_admin: bool) -> str:
    admin_block = (
        "\n<b>Admin Tools</b>\n"
        "/admin - open the admin panel\n"
        "/ban_token SYMBOL - block a token\n"
        "/unban_token SYMBOL - restore a token\n"
        "/banned_tokens - show current blacklist"
        if is_admin
        else ""
    )
    return (
        "<b>Help Center</b>\n"
        "This bot sends MEXC spot/futures spread alerts directly into your chat.\n\n"
        "<b>Main Commands</b>\n"
        "/start - subscribe this chat to alerts\n"
        "/stop - stop alerts for this chat\n"
        "/about - learn what the bot does\n"
        "/help - open this guide"
        f"{admin_block}\n\n"
        "<b>How Alerts Work</b>\n"
        "1. The parser detects an open spread.\n"
        "2. The bot sends the first alert.\n"
        "3. Deepen and close updates arrive as replies to the latest alert for that token.\n\n"
        "<b>Tip</b>\n"
        "Use the buttons below to jump between panels quickly."
    )


def _about_text() -> str:
    return (
        "<b>About MEXC Spread Bot</b>\n"
        "This bot tracks spread events between spot and futures markets on MEXC and turns raw parser signals into readable Telegram alerts.\n\n"
        "<b>What You Get</b>\n"
        "• open alerts when a spread appears\n"
        "• deepen alerts when the same spread reaches a new local maximum\n"
        "• close alerts when it aligns back toward the mean\n"
        "• quick Spot / Futures buttons for fast manual review\n\n"
        "<b>How The Project Is Built</b>\n"
        "• parser/backend detects and pushes events into an asyncio queue\n"
        "• bot layer consumes events and formats them for Telegram\n"
        "• both parts run inside one async application process\n\n"
        "<b>Creators</b>\n"
        "Built by the project team: parser/backend contributor plus bot/interface contributor.\n\n"
        "<b>Repository</b>\n"
        "https://github.com/Tenyokj/parser_fucha_dev\n\n"
        "<b>Current Notes</b>\n"
        "• subscriptions are kept in runtime memory\n"
        "• token blacklist is persisted for admin moderation\n"
        "• alert text is optimized for quick scanning in chat"
    )


def _admin_text(
    *,
    subscribers: SubscriberRegistry,
    blacklist: TokenBlacklistRegistry,
    admin_ids: set[int],
    started_at: datetime,
) -> str:
    return (
        "<b>Admin Panel</b>\n"
        "Moderation and health overview for the bot runtime.\n\n"
        "<b>Live Stats</b>\n"
        f"• subscribers: <code>{len(subscribers.list_chat_ids())}</code>\n"
        f"• blacklisted tokens: <code>{len(blacklist.list_symbols())}</code>\n"
        f"• configured admins: <code>{len(admin_ids)}</code>\n"
        f"• uptime: <code>{_format_uptime(started_at)}</code>\n\n"
        "<b>Actions</b>\n"
        "• <code>/ban_token SYMBOL</code> to suppress a token\n"
        "• <code>/unban_token SYMBOL</code> to remove a suppression\n"
        "• <code>/banned_tokens</code> to inspect the blacklist\n\n"
        "<b>Note</b>\n"
        "The bot blocks blacklisted symbols before sending alerts to subscribers."
    )


def _format_uptime(started_at: datetime) -> str:
    seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())
    if seconds < 60:
        return f"{seconds} sec"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        if sec == 0:
            return f"{minutes} min"
        return f"{minutes} min {sec} sec"
    hours, rem_minutes = divmod(minutes, 60)
    if rem_minutes == 0:
        return f"{hours} h"
    return f"{hours} h {rem_minutes} min"
