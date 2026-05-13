from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping

from bot.keyboards import market_links_keyboard


EventLike = Mapping[str, Any] | Any


def format_event_message(event: EventLike) -> tuple[str, object | None]:
    event_type = _event_type(event)

    if event_type == "deepen":
        text = _format_deepen(event)
        keyboard = market_links_keyboard(symbol=_symbol(event))
    elif event_type == "close":
        text = _format_close(event)
        keyboard = None
    else:
        text = _format_open(event)
        keyboard = market_links_keyboard(symbol=_symbol(event))
    return text, keyboard


def event_thread_key(event: EventLike) -> str:
    return str(
        _value(
            event,
            "spread_id",
            "event_id",
            "id",
            "key",
            "symbol",
            "pair",
            default="unknown",
        )
    )


def _format_open(event: EventLike) -> str:
    emoji, direction = _direction_style(event)
    return "\n".join(
        [
            f"{emoji} <b>{direction}</b> <b>#{escape(_symbol(event))}</b> Spread "
            f"<b>{_signed_percent(event, 'spread_pct', 'spread_percent', 'spread')}</b> detected",
            f"🎰 Price SPOT <code>{_usd(event, 'spot_price')}</code>",
            f"🎰 Price FUT  <code>{_usd(event, 'fut_price', 'futures_price', 'future_price')}</code>",
            f"📊 24h Vol <code>{_compact_usd(event, 'volume_24h_usd')}</code>",
        ]
    )


def _format_deepen(event: EventLike) -> str:
    emoji, direction = _direction_style(event)
    return "\n".join(
        [
            f"{emoji} <b>{direction}</b> <b>#{escape(_symbol(event))}</b> Spread "
            f"<b>{_signed_percent(event, 'spread_pct', 'spread_percent', 'spread')}</b> detected (deepened)",
            f"🎰 Price SPOT <code>{_usd(event, 'spot_price')}</code>",
            f"🎰 Price FUT  <code>{_usd(event, 'fut_price', 'futures_price', 'future_price')}</code>",
            f"📊 24h Vol <code>{_compact_usd(event, 'volume_24h_usd')}</code>",
        ]
    )


def _format_close(event: EventLike) -> str:
    return (
        f"✅ <b>#{escape(_symbol(event))}</b> Aligned in "
        f"<b>{escape(_format_duration(_value(event, 'duration_sec', default=None)))}</b> "
        f"| daily peak was <b>{_absolute_percent(event, 'daily_peak_pct')}</b>"
    )


def _event_type(event: EventLike) -> str:
    raw_value = str(_value(event, "event_type", "type", "action", "status", default="open"))
    raw_value = raw_value.strip().lower()
    if raw_value in {"deepen", "deepen_spread", "update"}:
        return "deepen"
    if raw_value in {"close", "closed", "close_spread"}:
        return "close"
    return "open"


def _symbol(event: EventLike) -> str:
    return str(_value(event, "symbol", "pair", "instrument", default="UNKNOWN"))


def _timestamp(event: EventLike) -> str:
    raw = _value(event, "timestamp", "created_at", "detected_at", default=None)
    if raw is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%d %H:%M:%S")
    return str(raw)


def _percent(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}%"
    except (TypeError, ValueError):
        return escape(str(value))


def _signed_percent(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return escape(str(value))


def _absolute_percent(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"{abs(float(value)):.1f}%"
    except (TypeError, ValueError):
        return escape(str(value))


def _number(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.8f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return escape(str(value))


def _usd(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        return f"${float(value):,.6f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return escape(str(value))


def _compact_usd(event: EventLike, *names: str) -> str:
    value = _value(event, *names, default=None)
    if value is None:
        return "n/a"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return escape(str(value))

    abs_amount = abs(amount)
    if abs_amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}B"
    if abs_amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if abs_amount >= 1_000:
        return f"${amount / 1_000:.1f}K"
    return f"${amount:.0f}"


def _format_duration(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return str(value)

    if seconds >= 120:
        minutes = max(1, round(seconds / 60))
        return f"{minutes} min"
    return f"{seconds} sec"


def _direction_style(event: EventLike) -> tuple[str, str]:
    direction = str(_value(event, "direction", default="LONG")).strip().upper()
    if direction == "SHORT":
        return "🔴", "SHORT"
    return "🟢", "LONG"


def _value(event: EventLike, *names: str, default: Any = None) -> Any:
    data = _to_mapping(event)
    for name in names:
        if name in data and data[name] is not None:
            return data[name]
    return default


def _to_mapping(event: EventLike) -> dict[str, Any]:
    if isinstance(event, Mapping):
        return dict(event)
    if is_dataclass(event):
        return asdict(event)
    if hasattr(event, "__dict__"):
        return vars(event)
    return {}
