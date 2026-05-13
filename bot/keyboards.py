from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


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
