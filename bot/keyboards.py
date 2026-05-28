from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

REPO_URL = "https://github.com/Tenyokj/parser_fucha_dev"


def build_market_url(symbol: str, *, futures: bool = False) -> str:
    market_symbol = f"{symbol.upper()}_USDT"
    if futures:
        return f"https://futures.mexc.com/exchange/{market_symbol}"
    return f"https://www.mexc.com/exchange/{market_symbol}"


def market_links_keyboard(
    *,
    symbol: str | None,
) -> InlineKeyboardMarkup | None:
    if not symbol:
        return None

    builder = InlineKeyboardBuilder()
    builder.button(text="Spot", url=build_market_url(symbol))
    builder.button(text="Futures", url=build_market_url(symbol, futures=True))
    builder.adjust(2)
    return builder.as_markup()


def help_panel_keyboard(*, is_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="About Bot", callback_data="panel:about")
    builder.button(text="Repository", url=REPO_URL)
    if is_admin:
        builder.button(text="Admin Panel", callback_data="panel:admin")
    builder.adjust(2, 1)
    return builder.as_markup()


def about_panel_keyboard(*, is_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Repository", url=REPO_URL)
    builder.button(text="Help", callback_data="panel:help")
    if is_admin:
        builder.button(text="Admin Panel", callback_data="panel:admin")
    builder.adjust(2, 1)
    return builder.as_markup()


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Refresh", callback_data="panel:admin")
    builder.button(text="Blacklist", callback_data="panel:blacklist")
    builder.button(text="Help", callback_data="panel:help")
    builder.button(text="About", callback_data="panel:about")
    builder.adjust(2, 2)
    return builder.as_markup()
